(function () {
    const labels = document.currentScript.dataset;
    const dishNames = new Map(["Чизбургер", "Картофель фри", "Лимонад", "Маргарита", "Пепперони", "Филадельфия", "Сет на двоих"].map((name, index) => [name, labels["dish" + (index + 1)]]));
    var STORAGE_KEY = "bitebox_favorites";
    var SVG_NS = "http://www.w3.org/2000/svg";
    var HEART_PATH =
        "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z";

    function isValidItem(item) {
        return (
            item &&
            typeof item.id === "string" &&
            typeof item.name === "string" &&
            typeof item.restaurant === "string" &&
            isFinite(Number(item.price))
        );
    }

    function readFavorites() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            var parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed) ? parsed.filter(isValidItem) : [];
        } catch (e) {
            return [];
        }
    }

    function writeFavorites(list) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
        } catch (e) {}
    }

    function formatPrice(value) {
        return Number(value).toLocaleString(document.documentElement.lang || "en") + " ₸";
    }

    function createHeartIcon() {
        var svg = document.createElementNS(SVG_NS, "svg");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("aria-hidden", "true");
        var path = document.createElementNS(SVG_NS, "path");
        path.setAttribute("d", HEART_PATH);
        svg.appendChild(path);
        return svg;
    }

    function toggleFavorite(item) {
        var list = readFavorites();
        var index = list.findIndex(function (entry) {
            return entry.id === item.id;
        });
        if (index >= 0) {
            list.splice(index, 1);
        } else {
            list.push(item);
        }
        writeFavorites(list);
    }

    function removeFavorite(id) {
        writeFavorites(
            readFavorites().filter(function (entry) {
                return entry.id !== id;
            })
        );
    }

    function syncHearts() {
        var saved = Object.create(null);
        readFavorites().forEach(function (entry) {
            saved[entry.id] = true;
        });
        document.querySelectorAll(".js-fav").forEach(function (button) {
            if (!button.querySelector("svg")) {
                button.appendChild(createHeartIcon());
            }
            var active = Boolean(saved[button.dataset.favId]);
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
            button.setAttribute(
                "aria-label",
                active ? labels.removeHeart : labels.add
            );
        });
    }

    function groupByRestaurant(list) {
        var groups = [];
        var index = Object.create(null);
        list.forEach(function (entry) {
            if (!(entry.restaurant in index)) {
                index[entry.restaurant] = groups.length;
                groups.push({ restaurant: entry.restaurant, items: [] });
            }
            groups[index[entry.restaurant]].items.push(entry);
        });
        return groups;
    }

    function createCard(entry) {
        var col = document.createElement("div");
        col.className = "col-12 col-sm-6 col-lg-4";

        var card = document.createElement("div");
        card.className = "bb-card d-flex justify-content-between align-items-center gap-3 h-100";

        var info = document.createElement("div");
        var name = document.createElement("div");
        name.className = "fw-bold";
        name.textContent = dishNames.get(entry.name) || entry.name;
        var price = document.createElement("div");
        price.className = "bb-price";
        price.textContent = formatPrice(entry.price);
        info.appendChild(name);
        info.appendChild(price);

        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "btn btn-bb-outline js-fav-remove";
        remove.dataset.favId = entry.id;
        remove.textContent = labels.remove;

        card.appendChild(info);
        card.appendChild(remove);
        col.appendChild(card);
        return col;
    }

    function renderFavorites() {
        var list = document.getElementById("fav-list");
        var empty = document.getElementById("fav-empty");
        if (!list || !empty) {
            return;
        }

        var favorites = readFavorites();
        list.textContent = "";
        empty.classList.toggle("d-none", favorites.length > 0);
        list.classList.toggle("d-none", favorites.length === 0);

        groupByRestaurant(favorites).forEach(function (group) {
            var section = document.createElement("section");
            section.className = "mb-4";

            var title = document.createElement("h2");
            title.className = "h5 bb-group-title mb-3";
            title.textContent = group.restaurant;

            var row = document.createElement("div");
            row.className = "row g-3";
            group.items.forEach(function (entry) {
                row.appendChild(createCard(entry));
            });

            section.appendChild(title);
            section.appendChild(row);
            list.appendChild(section);
        });
    }

    document.addEventListener("click", function (event) {
        var heart = event.target.closest(".js-fav");
        if (heart) {
            event.preventDefault();
            toggleFavorite({
                id: heart.dataset.favId,
                name: heart.dataset.name,
                restaurant: heart.dataset.restaurant,
                price: Number(heart.dataset.price)
            });
            syncHearts();
            renderFavorites();
            return;
        }

        var remove = event.target.closest(".js-fav-remove");
        if (remove) {
            event.preventDefault();
            removeFavorite(remove.dataset.favId);
            renderFavorites();
            syncHearts();
        }
    });

    window.addEventListener("storage", function (event) {
        if (event.key === STORAGE_KEY || event.key === null) {
            syncHearts();
            renderFavorites();
        }
    });

    window.addEventListener("pageshow", function () {
        syncHearts();
        renderFavorites();
    });

    syncHearts();
    renderFavorites();
})();
