/**
 * command-bar.js - Cmd+K command bar for Flywheel.
 *
 * Provides quick access to skills, work items, and actions via
 * keyboard shortcut. Fetches searchable items from /api/search.
 */

const commandBar = {
  overlay: null,
  input: null,
  resultsList: null,
  items: [],
  filteredItems: [],
  selectedIndex: -1,
  isOpen: false,
  debounceTimer: null,

  // Static actions always available
  staticActions: [
    { type: "action", label: "Add Meeting", url: "/agenda?action=add-meeting", icon: "zap" },
    { type: "action", label: "Upload Document", url: "/onboarding", icon: "zap" },
    { type: "action", label: "Export Data", url: "/export", icon: "zap" },
    { type: "action", label: "View Dashboard", url: "/dashboard", icon: "zap" },
  ],

  init() {
    this.overlay = document.getElementById("command-bar-overlay");
    this.input = document.getElementById("command-bar-input");
    this.resultsList = document.getElementById("command-bar-results");

    if (!this.overlay || !this.input || !this.resultsList) return;

    // Global keyboard shortcut
    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        this.toggle();
      }
      if (e.key === "Escape" && this.isOpen) {
        e.preventDefault();
        this.close();
      }
    });

    // Backdrop click to close
    this.overlay.addEventListener("click", (e) => {
      if (e.target === this.overlay) this.close();
    });

    // Input filtering with debounce
    this.input.addEventListener("input", () => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => this.filter(), 150);
    });

    // Keyboard navigation inside results
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        this.selectedIndex = Math.min(this.selectedIndex + 1, this.filteredItems.length - 1);
        this.renderResults();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
        this.renderResults();
      } else if (e.key === "Enter" && this.selectedIndex >= 0) {
        e.preventDefault();
        this.selectItem(this.filteredItems[this.selectedIndex]);
      }
    });
  },

  toggle() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  },

  open() {
    this.isOpen = true;
    this.overlay.classList.add("active");
    this.input.value = "";
    this.selectedIndex = -1;
    this.input.focus();
    this.loadItems();
  },

  close() {
    this.isOpen = false;
    this.overlay.classList.remove("active");
    this.input.value = "";
    this.filteredItems = [];
    this.selectedIndex = -1;
    this.resultsList.innerHTML = "";
  },

  loadItems() {
    fetch("/api/search")
      .then((r) => r.json())
      .then((data) => {
        this.items = data;
        this.showRecentsOrAll();
      })
      .catch(() => {
        this.items = this.staticActions;
        this.showRecentsOrAll();
      });
  },

  showRecentsOrAll() {
    const recents = this.getRecentCommands();
    if (recents.length > 0 && !this.input.value) {
      // Show recents at top, then all items
      const recentItems = recents
        .map((url) => this.items.find((i) => i.url === url))
        .filter(Boolean);
      const rest = this.items.filter((i) => !recents.includes(i.url));
      this.filteredItems = [...recentItems, ...rest];
    } else {
      this.filteredItems = this.items;
    }
    this.renderResults();
  },

  filter() {
    const query = (this.input.value || "").toLowerCase().trim();
    if (!query) {
      this.showRecentsOrAll();
      return;
    }
    this.filteredItems = this.items.filter((item) =>
      item.label.toLowerCase().includes(query)
    );
    this.selectedIndex = this.filteredItems.length > 0 ? 0 : -1;
    this.renderResults();
  },

  renderResults() {
    this.resultsList.innerHTML = "";
    this.filteredItems.forEach((item, index) => {
      const li = document.createElement("li");
      li.className = "cb-result" + (index === this.selectedIndex ? " cb-selected" : "");
      li.innerHTML = `
        <span class="cb-icon">${this.getIcon(item.type)}</span>
        <span class="cb-label">${this.escapeHtml(item.label)}</span>
        <span class="cb-type-badge">${item.type}</span>
      `;
      li.addEventListener("click", () => this.selectItem(item));
      li.addEventListener("mouseenter", () => {
        this.selectedIndex = index;
        this.renderResults();
      });
      this.resultsList.appendChild(li);
    });
  },

  selectItem(item) {
    if (!item) return;
    this.saveRecentCommand(item.url);
    this.close();
    window.location.href = item.url;
  },

  getIcon(type) {
    switch (type) {
      case "skill": return "&#9654;";   // play
      case "work":  return "&#128197;"; // calendar
      case "action": return "&#9889;";  // lightning
      default: return "&#8226;";        // bullet
    }
  },

  escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  },

  // Recent commands (localStorage)
  getRecentCommands() {
    try {
      return JSON.parse(localStorage.getItem("flywheel_recent_commands") || "[]");
    } catch {
      return [];
    }
  },

  saveRecentCommand(url) {
    try {
      let recents = this.getRecentCommands().filter((u) => u !== url);
      recents.unshift(url);
      recents = recents.slice(0, 5);
      localStorage.setItem("flywheel_recent_commands", JSON.stringify(recents));
    } catch {
      // localStorage unavailable
    }
  },
};
