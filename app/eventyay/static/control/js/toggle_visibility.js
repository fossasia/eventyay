document.addEventListener("click", function (e) {
    const btn = e.target.closest(".toggle-visibility");
    if (!btn) return;

    const input = document.querySelector(btn.dataset.target);
    const icon = btn.querySelector("i");

    if (!input) return;

    if (input.type === "password") {
        input.type = "text";
        icon.classList.replace("fa-eye", "fa-eye-slash");
    } else {
        input.type = "password";
        icon.classList.replace("fa-eye-slash", "fa-eye");
    }
});