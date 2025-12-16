/// <reference lib="dom" />

import { ChatController } from "./modules/chat/ChatController";

window.addEventListener("DOMContentLoaded", () => {
  const messages = document.getElementById("messages")!;
  const input = document.getElementById("input") as HTMLTextAreaElement;
  const send = document.getElementById("send")!;

  const controller = new ChatController(messages, input);

  send.addEventListener("click", () => {
    if (!input.value.trim()) return;
    controller.sendUserMessage(input.value);
    input.value = "";
  });
});
