import { ChatMessage } from "../llm/LLMService";
import { MockLLMService } from "../llm/MockLLMService";

export class ChatController {
  private messages: ChatMessage[] = [];
  private llm = new MockLLMService();

  constructor(
    private messagesEl: HTMLElement,
    private inputEl: HTMLTextAreaElement
  ) {}

  async sendUserMessage(text: string) {
    const userMsg: ChatMessage = { role: "user", content: text };
    this.messages.push(userMsg);
    this.renderMessage(userMsg);

    const reply = await this.llm.sendMessage(this.messages);
    this.messages.push(reply);
    this.renderMessage(reply);
  }

  private renderMessage(msg: ChatMessage) {
    const div = document.createElement("div");
    div.className = `msg ${msg.role}`;
    div.textContent = msg.content;
    this.messagesEl.appendChild(div);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }
}
