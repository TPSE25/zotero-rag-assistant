import { ChatMessage, LLMService } from "./LLMService";

export class MockLLMService implements LLMService {
  async sendMessage(messages: ChatMessage[]): Promise<ChatMessage> {
    const lastUserMessage = messages[messages.length - 1].content;

    // Fake delay (UX realism)
    await new Promise((r) => setTimeout(r, 800));

    return {
      role: "assistant",
      content: `🤖 Mock response to: "${lastUserMessage}"\n\n(This is a placeholder LLM response.)`,
    };
  }
}
