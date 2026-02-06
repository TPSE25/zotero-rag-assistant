import { Source } from "./ragClient";
import {getPref} from "../utils/prefs";

export type ChatRole = "user" | "assistant";

export interface ChatSession {
    id: string;
    title: string;
    createdAt: number;
}

export interface ChatMessage {
    id: string;
    sessionId: string;
    role: ChatRole;
    content: string;
    createdAt: number;
    sources?: Source[];
}

function gen_uid(): string {
    return `id_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export class ChatDB {
    private static DB_NAME = "rag_assistant_chat";
    private static DB_VERSION = 1;

    private dbPromise: Promise<IDBDatabase> | null = null;
    private idbFactory: IDBFactory;

    constructor(idbFactory: IDBFactory) {
        this.idbFactory = idbFactory;
    }

    private getOutputDir(): string {
        try {
            return (getPref("chatOutputDir") ?? "").trim();
        } catch {
            return "";
        }
    }

    private formatSessionText(session: ChatSession, messages: ChatMessage[]): string {
        const iso = (ms: number) => new Date(ms).toISOString();

        const lines: string[] = [];
        lines.push(`# ${session.title}`);
        lines.push(`sessionId: ${session.id}`);
        lines.push(`createdAt: ${iso(session.createdAt)}`);
        lines.push("");

        for (const m of messages) {
            lines.push("---");
            lines.push(`[${iso(m.createdAt)}] ${m.role}`);
            lines.push(m.content ?? "");
            if (m.sources?.length) {
                lines.push("");
                lines.push(`sources: ${JSON.stringify(m.sources)}`);
            }
            lines.push("");
        }

        return lines.join("\n");
    }

    private async writeSessionToDisk(sessionId: string): Promise<void> {
        const outDir = this.getOutputDir();
        if (!outDir) return;

        try {
            await IOUtils.makeDirectory(outDir, {
                createAncestors: true,
                ignoreExisting: true,
            });

            const session = await this.getSession(sessionId);
            if (!session) return;

            const messages = await this.listMessages(sessionId);
            const text = this.formatSessionText(session, messages);

            const targetPath = PathUtils.join(outDir, `${sessionId}.txt`);
            const tmpPath = `${targetPath}.tmp_${Math.random().toString(16).slice(2)}`;

            await IOUtils.writeUTF8(targetPath, text, {
                tmpPath,
                mode: "overwrite",
            });
        } catch (e) {
            const err = e instanceof Error ? e : new Error(typeof e === "string" ? e : JSON.stringify(e));
            Zotero.logError(err);
        }
    }

    private async removeSessionFromDisk(sessionId: string): Promise<void> {
        const outDir = this.getOutputDir();
        if (!outDir) return;

        try {
            const targetPath = PathUtils.join(outDir, `${sessionId}.txt`);
            await IOUtils.remove(targetPath, { ignoreAbsent: true });
        } catch (e) {
            const err = e instanceof Error ? e : new Error(typeof e === "string" ? e : JSON.stringify(e));
            Zotero.logError(err);
        }
    }

    private open(): Promise<IDBDatabase> {
        if (this.dbPromise) return this.dbPromise;

        this.dbPromise = new Promise((resolve, reject) => {
            const req = this.idbFactory.open(ChatDB.DB_NAME, ChatDB.DB_VERSION);

            req.onupgradeneeded = () => {
                const db = req.result;

                if (!db.objectStoreNames.contains("sessions")) {
                    const s = db.createObjectStore("sessions", { keyPath: "id" });
                    s.createIndex("by_updatedAt", "createdAt", { unique: false });
                }

                if (!db.objectStoreNames.contains("messages")) {
                    const m = db.createObjectStore("messages", { keyPath: "id" });
                    m.createIndex("by_session_createdAt", ["sessionId", "createdAt"], { unique: false });
                    m.createIndex("by_session", "sessionId", { unique: false });
                }
            };

            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });

        return this.dbPromise;
    }

    private async tx<T>(storeNames: string[], mode: IDBTransactionMode, fn: (tx: IDBTransaction) => Promise<T>): Promise<T> {
        const db = await this.open();
        const tx = db.transaction(storeNames, mode);
        const p = fn(tx);
        return await new Promise<T>((resolve, reject) => {
            tx.oncomplete = async () => resolve(await p);
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error);
        });
    }

    async listSessions(): Promise<ChatSession[]> {
        return this.tx(["sessions"], "readonly", async (tx) => {
            const store = tx.objectStore("sessions");
            const idx = store.index("by_updatedAt");
            const req = idx.getAll();
            const sessions = await reqToPromise<ChatSession[]>(req);
            return sessions.sort((a, b) => b.createdAt - a.createdAt);
        });
    }

    async getSession(id: string): Promise<ChatSession | null> {
        return this.tx(["sessions"], "readonly", async (tx) => {
            const req = tx.objectStore("sessions").get(id);
            return (await reqToPromise<ChatSession | undefined>(req)) ?? null;
        });
    }

    async createSession(title = "New chat"): Promise<ChatSession> {
        const now = Date.now();
        const session: ChatSession = { id: gen_uid(), title, createdAt: now };
        await this.tx(["sessions"], "readwrite", async (tx) => {
            tx.objectStore("sessions").put(session);
        });
        await this.writeSessionToDisk(session.id);
        return session;
    }

    async renameSession(sessionId: string, title: string): Promise<void> {
        await this.tx(["sessions"], "readwrite", async (tx) => {
            const store = tx.objectStore("sessions");
            const s = (await reqToPromise<ChatSession | undefined>(store.get(sessionId))) ?? null;
            if (!s) return;
            s.title = title;
            store.put(s);
        });
        await this.writeSessionToDisk(sessionId);
    }

    async deleteSession(sessionId: string): Promise<void> {
        await this.tx(["sessions", "messages"], "readwrite", async (tx) => {
            tx.objectStore("sessions").delete(sessionId);

            const msgStore = tx.objectStore("messages");
            const idx = msgStore.index("by_session");
            const keysReq = idx.getAllKeys(sessionId);
            const keys = await reqToPromise<string[]>(keysReq);
            keys.forEach((k) => msgStore.delete(k));
        });
        await this.removeSessionFromDisk(sessionId);
    }

    async listMessages(sessionId: string): Promise<ChatMessage[]> {
        return this.tx(["messages"], "readonly", async (tx) => {
            const store = tx.objectStore("messages");
            const idx = store.index("by_session");

            const req = idx.getAll(sessionId);
            const msgs = await reqToPromise<ChatMessage[]>(req);

            msgs.sort((a, b) => a.createdAt - b.createdAt);
            return msgs;
        });
    }

    async addMessage(msg: Omit<ChatMessage, "id" | "createdAt"> & { id?: string; createdAt?: number }): Promise<ChatMessage> {
        const full: ChatMessage = {
            id: msg.id ?? gen_uid(),
            createdAt: msg.createdAt ?? Date.now(),
            sessionId: msg.sessionId,
            role: msg.role,
            content: msg.content,
            sources: msg.sources,
        };
        await this.tx(["messages"], "readwrite", async (tx) => {
            tx.objectStore("messages").put(full);
        });
        await this.writeSessionToDisk(full.id);
        return full;
    }

    async updateMessage(id: string, patch: Partial<Pick<ChatMessage, "content" | "sources">>): Promise<void> {
        let sessionId: string | null = null;
        await this.tx(["messages"], "readwrite", async (tx) => {
            const store = tx.objectStore("messages");
            const m = (await reqToPromise<ChatMessage | undefined>(store.get(id))) ?? null;
            if (!m) return;
            sessionId = m.sessionId;
            if (patch.content !== undefined) m.content = patch.content;
            if (patch.sources !== undefined) m.sources = patch.sources;
            store.put(m);
        });
        if (!sessionId) throw new Error(`Message ${id} not found`);
        await this.writeSessionToDisk(sessionId);
    }
}

function reqToPromise<T>(req: IDBRequest): Promise<T> {
    return new Promise((resolve, reject) => {
        req.onsuccess = () => resolve(req.result as T);
        req.onerror = () => reject(req.error);
    });
}