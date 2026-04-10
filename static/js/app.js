document.addEventListener("DOMContentLoaded", function () {
    initConfirmDialogs();
    initMobileNavToggle();
    initMonthSelectorAutoSubmit();
    initDropdownMenus();
    initFlashMessageAutoDismiss();
});

function initConfirmDialogs() {
    document.querySelectorAll("[data-confirm]").forEach(function (element) {
        element.addEventListener("click", function (e) {
            var message = this.getAttribute("data-confirm") || "Are you sure you want to delete this item?";
            if (!confirm(message)) {
                e.preventDefault();
                e.stopImmediatePropagation();
            }
        });
    });

    document.querySelectorAll("form[data-confirm-submit]").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            var message = this.getAttribute("data-confirm-submit") || "Are you sure you want to proceed?";
            if (!confirm(message)) {
                e.preventDefault();
                e.stopImmediatePropagation();
            }
        });
    });
}

function initMobileNavToggle() {
    var toggleBtn = document.getElementById("mobile-nav-toggle");
    var mobileMenu = document.getElementById("mobile-nav-menu");

    if (!toggleBtn || !mobileMenu) {
        return;
    }

    toggleBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        mobileMenu.classList.toggle("hidden");
        var isExpanded = !mobileMenu.classList.contains("hidden");
        toggleBtn.setAttribute("aria-expanded", String(isExpanded));
    });

    document.addEventListener("click", function (e) {
        if (!mobileMenu.classList.contains("hidden") && !mobileMenu.contains(e.target) && !toggleBtn.contains(e.target)) {
            mobileMenu.classList.add("hidden");
            toggleBtn.setAttribute("aria-expanded", "false");
        }
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && !mobileMenu.classList.contains("hidden")) {
            mobileMenu.classList.add("hidden");
            toggleBtn.setAttribute("aria-expanded", "false");
        }
    });
}

function initMonthSelectorAutoSubmit() {
    document.querySelectorAll("select[data-auto-submit]").forEach(function (select) {
        select.addEventListener("change", function () {
            var form = this.closest("form");
            if (form) {
                form.submit();
            }
        });
    });

    document.querySelectorAll("input[type='month'][data-auto-submit]").forEach(function (input) {
        input.addEventListener("change", function () {
            var form = this.closest("form");
            if (form) {
                form.submit();
            }
        });
    });

    document.querySelectorAll("input[type='date'][data-auto-submit]").forEach(function (input) {
        input.addEventListener("change", function () {
            var form = this.closest("form");
            if (form) {
                form.submit();
            }
        });
    });
}

function initDropdownMenus() {
    document.querySelectorAll("[data-dropdown-toggle]").forEach(function (trigger) {
        var targetId = trigger.getAttribute("data-dropdown-toggle");
        var dropdown = document.getElementById(targetId);

        if (!dropdown) {
            return;
        }

        trigger.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();

            document.querySelectorAll("[data-dropdown-menu].active").forEach(function (openDropdown) {
                if (openDropdown !== dropdown) {
                    openDropdown.classList.add("hidden");
                    openDropdown.classList.remove("active");
                }
            });

            dropdown.classList.toggle("hidden");
            dropdown.classList.toggle("active");

            var isExpanded = !dropdown.classList.contains("hidden");
            trigger.setAttribute("aria-expanded", String(isExpanded));
        });
    });

    document.addEventListener("click", function (e) {
        document.querySelectorAll("[data-dropdown-menu].active").forEach(function (dropdown) {
            if (!dropdown.contains(e.target)) {
                dropdown.classList.add("hidden");
                dropdown.classList.remove("active");

                var triggerId = dropdown.getAttribute("id");
                if (triggerId) {
                    var trigger = document.querySelector("[data-dropdown-toggle='" + triggerId + "']");
                    if (trigger) {
                        trigger.setAttribute("aria-expanded", "false");
                    }
                }
            }
        });
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            document.querySelectorAll("[data-dropdown-menu].active").forEach(function (dropdown) {
                dropdown.classList.add("hidden");
                dropdown.classList.remove("active");

                var triggerId = dropdown.getAttribute("id");
                if (triggerId) {
                    var trigger = document.querySelector("[data-dropdown-toggle='" + triggerId + "']");
                    if (trigger) {
                        trigger.setAttribute("aria-expanded", "false");
                        trigger.focus();
                    }
                }
            });
        }
    });
}

function initFlashMessageAutoDismiss() {
    var autoDismissDelay = 5000;
    var fadeOutDuration = 300;

    document.querySelectorAll("[data-flash-message]").forEach(function (flash) {
        var delay = parseInt(flash.getAttribute("data-flash-dismiss-delay") || String(autoDismissDelay), 10);

        setTimeout(function () {
            dismissFlashMessage(flash, fadeOutDuration);
        }, delay);
    });

    document.querySelectorAll("[data-flash-dismiss]").forEach(function (dismissBtn) {
        dismissBtn.addEventListener("click", function (e) {
            e.preventDefault();
            var flash = this.closest("[data-flash-message]");
            if (flash) {
                dismissFlashMessage(flash, fadeOutDuration);
            }
        });
    });
}

function dismissFlashMessage(element, duration) {
    element.style.transition = "opacity " + duration + "ms ease-out";
    element.style.opacity = "0";

    setTimeout(function () {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    }, duration);
}