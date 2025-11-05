const matchPasswords = (passwordField, confirmationFields) => {
    // Optional parameter: if no specific confirmation field is given, check all
    if (confirmationFields === undefined) {
        confirmationFields = document.querySelectorAll(".password_confirmation")
    }
    if (confirmationFields === undefined) return

    const password = passwordField.value

    confirmationFields.forEach((confirmationField, index) => {
        const confirmValue = confirmationField.value
        const confirmWith = confirmationField.dataset.confirmWith

        if (confirmWith && confirmWith === passwordField.name) {
            if (confirmValue && password) {
                if (confirmValue === password) {
                    confirmationField.parentNode
                        .querySelector(".password_strength_info")
                        .classList.add("d-none")
                } else {
                    confirmationField.parentNode
                        .querySelector(".password_strength_info")
                        .classList.remove("d-none")
                }
            } else {
                confirmationField.parentNode
                    .querySelector(".password_strength_info")
                    .classList.add("d-none")
            }
        }
    })

    // If a password field other than our own has been used, add the listener here
    if (
        !passwordField.classList.contains("password_strength") &&
        !passwordField.dataset.passwordListener
    ) {
        passwordField.addEventListener("keyup", () =>
            matchPasswords(passwordField),
        )
        passwordField.dataset.passwordListener = true
    }
}

const validatePasswordComplexity = (password) => {
    const errors = []

    if (password.length < 8) {
        errors.push("Password must be at least 8 characters long")
    }

    if (!/[a-zA-Z]/.test(password)) {
        errors.push("Password must contain at least one letter")
    }

    if (!/[0-9]/.test(password)) {
        errors.push("Password must contain at least one number")
    }

    if (!/[!@#$%^&*()_\-+=\[\\\]{}|;':",.<>/?`~]/.test(password)) {
        errors.push("Password must contain at least one special character")
    }

    const commonPasswords = [
        "password",
        "password123",
        "12345678",
        "qwerty",
        "abc123",
    ]
    if (commonPasswords.includes(password.toLowerCase())) {
        errors.push("This password is too common")
    }

    return errors
}

const updatePasswordStrength = (passwordField) => {
    const passwordStrengthBar = passwordField.parentNode.querySelector(
        ".password_strength_bar",
    )
    const passwordStrengthInfo = passwordField.parentNode.querySelector(
        ".password_strength_info",
    )

    if (!passwordField.value) {
        passwordStrengthBar.classList.remove("bg-success")
        passwordStrengthBar.classList.add("bg-warning")
        passwordStrengthBar.style.width = "0%"
        passwordStrengthBar.setAttribute("aria-valuenow", 0)
        passwordStrengthInfo.classList.add("d-none")
        return
    }

    const validationErrors = validatePasswordComplexity(passwordField.value);
    passwordStrengthInfo.textContent = "";

    if (validationErrors.length > 0) {
        passwordStrengthBar.classList.remove("bg-success", "bg-warning");
        passwordStrengthBar.classList.add("bg-danger");
        passwordStrengthBar.style.width = "20%";
        passwordStrengthBar.setAttribute("aria-valuenow", 1);

        const container = document.createElement("div");
        container.className = "password-validation-errors";

        validationErrors.forEach((err) => {
            const span = document.createElement("span");
            span.className = "d-block text-danger";

            const icon = document.createElement("i");
            icon.className = "fa fa-times-circle";
            icon.setAttribute("aria-hidden", "true");

            span.appendChild(icon);
            span.append(` ${err}`);
            container.appendChild(span);
        });
        passwordStrengthInfo.appendChild(container);
        passwordStrengthInfo.classList.remove("d-none");
    } else {
        const result = zxcvbn(passwordField.value);
        const crackTime = result.crack_times_display.online_no_throttling_10_per_second;

        passwordStrengthBar.classList.remove("bg-danger", "bg-warning", "bg-success");
        if (result.score < 1) {
            passwordStrengthBar.classList.add("bg-danger");
        } else if (result.score < 3) {
            passwordStrengthBar.classList.add("bg-warning");
        } else {
            passwordStrengthBar.classList.add("bg-success");
        }

        passwordStrengthBar.style.width = `${((result.score + 1) / 5) * 100}%`;
        passwordStrengthBar.setAttribute("aria-valuenow", result.score + 1);
        const p = document.createElement("p");
        p.className = "text-muted mb-0";

        const span = document.createElement("span");
        if (result.score >= 3) {
            span.className = "text-success";
            const icon = document.createElement("i");
            icon.className = "fa fa-check-circle";
            icon.setAttribute("aria-hidden", "true");
            span.appendChild(icon);
            span.append(` This password would take ${crackTime} to crack.`);
        } else {
            span.textContent = `This password would take ${crackTime} to crack.`;
        }

        p.appendChild(span);
        passwordStrengthInfo.appendChild(p);
        passwordStrengthInfo.classList.remove("d-none");
    }

    matchPasswords(passwordField)
}

const setupPasswordStrength = () => {
    document.querySelectorAll(".password_strength_info").forEach((element) => {
        element.classList.add("d-none")
    })
    document.querySelectorAll(".password_strength").forEach((passwordField) => {
        passwordField.addEventListener("keyup", () =>
            updatePasswordStrength(passwordField),
        )
    })

    let timer = null
    document
        .querySelectorAll(".password_confirmation")
        .forEach((confirmationField) => {
            confirmationField.addEventListener("keyup", () => {
                let passwordField
                const confirmWith = confirmationField.dataset.confirmWith

                if (confirmWith) {
                    passwordField = document.querySelector(
                        `[name=${confirmWith}]`,
                    )
                } else {
                    passwordField = document.querySelector(".password_strength")
                }

                if (timer !== null) clearTimeout(timer)
                timer = setTimeout(() => matchPasswords(passwordField), 400)
            })
        })
}

onReady(setupPasswordStrength)
