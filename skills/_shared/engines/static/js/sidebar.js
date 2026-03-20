/**
 * sidebar.js - Sidebar interactivity for Flywheel web app.
 *
 * Features:
 *   - Toggle sidebar collapse with localStorage persistence
 *   - Keyboard shortcut [ to toggle sidebar
 *   - Active link update on HTMX navigation (htmx:afterSwap)
 *   - SSE connection cleanup on navigation (htmx:beforeSwap)
 *   - Mobile hamburger toggle
 */

(function () {
  'use strict';

  // -----------------------------------------------------------------------
  // SSE connection tracking (prevents leaks on HTMX navigation)
  // -----------------------------------------------------------------------
  window._activeEventSources = window._activeEventSources || [];

  // -----------------------------------------------------------------------
  // Sidebar toggle
  // -----------------------------------------------------------------------
  function toggleSidebar() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    var collapsed = sidebar.dataset.collapsed === 'true';
    sidebar.dataset.collapsed = collapsed ? 'false' : 'true';
    localStorage.setItem('flywheel_sidebar_collapsed', !collapsed);
  }

  // Expose globally for onclick handlers
  window.toggleSidebar = toggleSidebar;

  // -----------------------------------------------------------------------
  // Mobile toggle
  // -----------------------------------------------------------------------
  function toggleMobileSidebar() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('mobile-open');
  }

  window.toggleMobileSidebar = toggleMobileSidebar;

  // -----------------------------------------------------------------------
  // Active link update
  // -----------------------------------------------------------------------
  var pathToPage = {
    '/agenda': 'agenda',
    '/companies': 'companies',
    '/skills': 'skills',
    '/dashboard': 'dashboard',
    '/integrations': 'integrations',
    '/export': 'export'
  };

  function updateActiveLink() {
    var path = window.location.pathname;
    var page = pathToPage[path] || '';

    var links = document.querySelectorAll('.sidebar-link');
    for (var i = 0; i < links.length; i++) {
      links[i].classList.remove('active');
    }

    if (page) {
      var links = document.querySelectorAll('.sidebar-link');
      for (var i = 0; i < links.length; i++) {
        var href = links[i].getAttribute('href');
        if (href && pathToPage[href] === page) {
          links[i].classList.add('active');
        }
      }
    }
  }

  // -----------------------------------------------------------------------
  // Event listeners
  // -----------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    // Restore collapsed state from localStorage
    var collapsed = localStorage.getItem('flywheel_sidebar_collapsed') === 'true';
    if (collapsed) {
      var sidebar = document.getElementById('sidebar');
      if (sidebar) {
        sidebar.dataset.collapsed = 'true';
      }
    }
  });

  // Keyboard shortcut: [ toggles sidebar (skip if focus in input/textarea)
  document.addEventListener('keydown', function (e) {
    if (e.key === '[' && !e.metaKey && !e.ctrlKey && !e.altKey) {
      var tag = document.activeElement ? document.activeElement.tagName : '';
      if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
        e.preventDefault();
        toggleSidebar();
      }
    }
  });

  // Update active link after HTMX content swap
  document.addEventListener('htmx:afterSwap', function () {
    updateActiveLink();
  });

  // Close active EventSource connections before HTMX navigation
  document.addEventListener('htmx:beforeSwap', function () {
    if (window._activeEventSources && window._activeEventSources.length > 0) {
      for (var i = 0; i < window._activeEventSources.length; i++) {
        try {
          window._activeEventSources[i].close();
        } catch (e) {
          // Ignore close errors
        }
      }
      window._activeEventSources = [];
    }
  });

})();
