export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface LLMService {
  sendMessage(messages: ChatMessage[]): Promise<ChatMessage>;
}
