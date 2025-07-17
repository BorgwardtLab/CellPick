// force_light_mode.js
document.addEventListener("DOMContentLoaded", function () {
    // Force light mode
    if (document.documentElement.getAttribute("data-theme") !== "light") {
        document.documentElement.setAttribute("data-theme", "light");
    }
    // Remove the theme switcher button if present
    var switcher = document.querySelector('.theme-switch-button');
    if (switcher) {
        switcher.style.display = 'none';
    }
}); 