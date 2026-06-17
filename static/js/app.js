// Main JavaScript for the public website and admin pages.
// This file uses vanilla JavaScript so the project stays lightweight.

document.addEventListener('DOMContentLoaded', () => {
    // Mobile navigation button for the public site header.
    const navToggle = document.querySelector('.nav-toggle');
    const navLinks = document.querySelector('.nav-links');

    if (navToggle && navLinks) {
        navToggle.addEventListener('click', () => {
            navLinks.classList.toggle('open');
        });
    }

    // Mobile sidebar button for the admin layout.
    const adminMenu = document.querySelector('.admin-menu');
    const adminSidebar = document.querySelector('.admin-sidebar');

    if (adminMenu && adminSidebar) {
        adminMenu.addEventListener('click', () => {
            adminSidebar.classList.toggle('open');
        });
    }

    // Allows users to close flash messages without refreshing the page.
    document.querySelectorAll('.flash-close').forEach((button) => {
        button.addEventListener('click', () => {
            button.closest('.flash')?.remove();
        });
    });
});

// Register the service worker so the site can behave like a PWA.
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch((error) => {
            console.warn('Service worker registration failed:', error);
        });
    });
}
