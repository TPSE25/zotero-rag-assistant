export async function pickOutputDir(window: Window) {
    const input = window.document.getElementById("chatOutputDir") as HTMLInputElement | null;
    if (!input) {
        throw new Error("Output directory input not found");
    }
    const picked = await new ztoolkit.FilePicker(
        "Select output directory",
        "folder",
        undefined,
        input.value || "",
        window
    ).open();
    input.value = picked ? picked : "";
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
    input.dispatchEvent(new window.Event("change", { bubbles: true }));
}
