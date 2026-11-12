(function () {
    if (window.__bbCartLoaded) {
        return;
    }
    window.__bbCartLoaded = true;

    const labels = document.currentScript.dataset;
    var busy = false;

    function getCookie(name) {
        var match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
        return match ? decodeURIComponent(match[1]) : "";
    }

    function post(url, data) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": getCookie("csrftoken"),
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: new URLSearchParams(data)
        }).then(function (response) {
            return response.json().then(function (payload) {
                return { status: response.status, data: payload };
            });
        });
    }

    function setBadge(count) {
        document.querySelectorAll("[data-cart-count]").forEach(function (el) {
            el.textContent = count;
        });
    }

    function showError(message) {
        var box = document.getElementById("cart-alert");
        if (box) {
            box.textContent = message;
            box.classList.remove("d-none");
        } else {
            window.alert(message);
        }
    }

    function hideError() {
        var box = document.getElementById("cart-alert");
        if (box) {
            box.classList.add("d-none");
        }
    }

    function applyCart(data) {
        setBadge(data.count);

        var root = document.getElementById("cart-root");
        if (!root) {
            return;
        }

        document.getElementById("cart-filled").classList.toggle("d-none", data.empty);
        document.getElementById("cart-empty").classList.toggle("d-none", !data.empty);

        root.querySelectorAll("[data-line]").forEach(function (row) {
            var info = data.lines[row.dataset.dishId];
            if (!info) {
                row.remove();
                return;
            }
            row.querySelector("[data-qty]").textContent = info.quantity;
            row.querySelector("[data-line-total]").textContent = info.total;
        });

        root.querySelectorAll("[data-subtotal]").forEach(function (el) {
            el.textContent = data.subtotal;
        });
        root.querySelectorAll("[data-total]").forEach(function (el) {
            el.textContent = data.total;
        });
        root.querySelectorAll("[data-restaurant]").forEach(function (el) {
            el.textContent = data.restaurant;
        });

        var warning = document.getElementById("cart-unavailable");
        if (warning) {
            warning.classList.toggle("d-none", !data.has_unavailable);
        }

        var checkout = document.getElementById("checkout-btn");
        if (checkout) {
            checkout.classList.toggle("disabled", !data.can_checkout);
            if (data.can_checkout) {
                checkout.removeAttribute("aria-disabled");
                checkout.removeAttribute("tabindex");
            } else {
                checkout.setAttribute("aria-disabled", "true");
                checkout.setAttribute("tabindex", "-1");
            }
        }
    }

    function sendCartChange(url, payload) {
        if (busy) {
            return;
        }
        busy = true;
        hideError();
        post(url, payload)
            .then(function (result) {
                if (result.status >= 400) {
                    showError(result.data.error || labels.updateError);
                    return;
                }
                applyCart(result.data);
            })
            .catch(function () {
                showError(labels.networkError);
            })
            .finally(function () {
                busy = false;
            });
    }

    function addDish(button, replace) {
        post(button.dataset.url, {
            dish_id: button.dataset.dishId,
            replace: replace ? "1" : "0"
        })
            .then(function (result) {
                if (result.status === 409 && result.data.conflict) {
                    var question = labels.replaceCart.replace(/\{(current|next)\}/g, function (_, key) {
                        return key === "current" ? result.data.current_restaurant : result.data.new_restaurant;
                    });
                    if (window.confirm(question)) {
                        addDish(button, true);
                    }
                    return;
                }
                if (result.status >= 400) {
                    window.alert(result.data.error || labels.addError);
                    return;
                }
                setBadge(result.data.count);
                var original = button.dataset.label || button.textContent;
                button.dataset.label = original;
                button.textContent = labels.added;
                setTimeout(function () {
                    button.textContent = original;
                }, 1200);
            })
            .catch(function () {
                window.alert(labels.networkError);
            });
    }

    document.addEventListener("click", function (event) {
        var addButton = event.target.closest(".js-add-to-cart");
        if (addButton) {
            event.preventDefault();
            addDish(addButton, false);
            return;
        }

        var actionButton = event.target.closest("[data-action]");
        var root = document.getElementById("cart-root");
        if (!actionButton || !root || !root.contains(actionButton)) {
            return;
        }

        var action = actionButton.dataset.action;
        if (action === "clear") {
            sendCartChange(root.dataset.clearUrl, {});
            return;
        }

        var row = actionButton.closest("[data-line]");
        if (!row) {
            return;
        }
        var dishId = row.dataset.dishId;
        var quantity = parseInt(row.querySelector("[data-qty]").textContent, 10) || 1;

        if (action === "inc") {
            sendCartChange(root.dataset.updateUrl, { dish_id: dishId, quantity: quantity + 1 });
        } else if (action === "dec") {
            sendCartChange(root.dataset.updateUrl, { dish_id: dishId, quantity: quantity - 1 });
        } else if (action === "remove") {
            sendCartChange(root.dataset.removeUrl, { dish_id: dishId });
        }
    });
})();