(function () {
    const labels = document.currentScript.dataset;
    const dishNames = new Map(["Чизбургер", "Картофель фри", "Лимонад", "Маргарита", "Пепперони", "Филадельфия", "Сет на двоих"].map((name, index) => [name, labels["dish" + (index + 1)]]));
    const translatedNames = document.getElementById("food-name-translations");
    if (translatedNames) {
        for (const [source, translated] of Object.entries(JSON.parse(translatedNames.textContent))) {
            dishNames.set(source, translated);
        }
    }
    const demoRestaurants = {
        "urban-burger": { photo: "burgerPhoto", delivery: 400, duration: "20–30" },
        "casa-pizza": { photo: "pizzaPhoto", delivery: 500, duration: "25–35" },
        "nori-sushi": { photo: "sushiPhoto", delivery: 600, duration: "30–40" }
    };
    const photoKeys = ["pizzaPhoto", "burgerPhoto", "sushiPhoto"];
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

    function addText(parent, tag, className, value) {
        const element = document.createElement(tag);
        element.className = className;
        element.textContent = value;
        parent.appendChild(element);
        return element;
    }

    function createCard(entry) {
        const col = document.createElement("div");
        col.className = "col-12 col-sm-6 col-lg-4";
        const card = document.createElement("article");
        card.className = "bb-card h-100";

        const demoKey = entry.id.match(/^(urban-burger|casa-pizza|nori-sushi)-[1-3]$/)?.[1];
        const demo = demoRestaurants[demoKey];
        const photoKey = demo?.photo || entry.photo;
        if (photoKeys.includes(photoKey) && labels[photoKey]) {
            const image = document.createElement("img");
            image.src = labels[photoKey];
            image.alt = "";
            image.loading = "lazy";
            image.className = "bb-fav-photo";
            card.appendChild(image);
        }

        const content = document.createElement("div");
        content.className = "bb-fav-card-content";
        if (entry.category) {
            addText(content, "p", "bb-fav-category", entry.category);
        }
        addText(content, "h3", "h5 fw-bold mb-0", dishNames.get(entry.name) || entry.name);
        addText(content, "p", "bb-price mb-0", formatPrice(entry.price));
        if (entry.description) {
            addText(content, "p", "bb-muted bb-fav-description mb-0", entry.description);
        }

        if (demo) {
            const minutes = document.documentElement.lang === "ru" ? "мин" : "min";
            addText(content, "p", "bb-fav-delivery mb-0",
                labels.delivery + ": " + demo.duration + " " + minutes + " · " + formatPrice(demo.delivery));
        }

        const actions = document.createElement("div");
        actions.className = "bb-fav-actions";
        const restaurantKey = demoKey || entry.restaurantKey;
        if (restaurantKey && labels.menuUrl) {
            const menuLink = addText(actions, "a", "bb-link", labels.menuLabel);
            const url = new URL(labels.menuUrl, window.location.href);
            url.searchParams.set("restaurant", restaurantKey);
            menuLink.href = url.href;
        }

        const remove = addText(actions, "button", "btn btn-bb-outline js-fav-remove", labels.remove);
        remove.type = "button";
        remove.dataset.favId = entry.id;
        content.appendChild(actions);
        card.appendChild(content);
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
            const row = heart.closest("[data-menu-category]");
            const photo = row?.querySelector(".restaurant-menu-photo");
            const photoKey = ["pizza", "burger", "sushi"].find((name) => photo?.classList.contains("photo-" + name));
            toggleFavorite({
                id: heart.dataset.favId,
                name: heart.dataset.name,
                restaurant: heart.dataset.restaurant,
                price: Number(heart.dataset.price),
                restaurantKey: heart.dataset.restaurantKey,
                category: row?.dataset.menuCategory,
                description: heart.dataset.description,
                photo: photoKey ? photoKey + "Photo" : undefined
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
