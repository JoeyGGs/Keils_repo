// Keil's Service Deli - Frontend JavaScript

// Mobile Navigation
document.addEventListener('DOMContentLoaded', function() {
    const navToggle = document.getElementById('navToggle');
    const navLinks = document.getElementById('navLinks');
    const navOverlay = document.getElementById('navOverlay');

    function openNav() {
        navLinks && navLinks.classList.add('open');
        navToggle && navToggle.classList.add('active');
        navOverlay && navOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function closeNav() {
        navLinks && navLinks.classList.remove('open');
        navToggle && navToggle.classList.remove('active');
        navOverlay && navOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    if (navToggle) {
        navToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            if (navLinks.classList.contains('open')) {
                closeNav();
            } else {
                openNav();
            }
        });
    }

    if (navOverlay) {
        navOverlay.addEventListener('click', closeNav);
    }

    // Close nav when a link is tapped
    if (navLinks) {
        navLinks.querySelectorAll('a').forEach(function(link) {
            link.addEventListener('click', closeNav);
        });
    }

    // Close on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeNav();
    });

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.3s';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// Confirm delete actions
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this?');
}

// Close modal when clicking outside
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});

// Close modal with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(modal => {
            modal.classList.remove('active');
        });
    }
});

// Format currency inputs
document.querySelectorAll('input[type="number"][step="0.01"]').forEach(input => {
    input.addEventListener('blur', function() {
        if (this.value) {
            this.value = parseFloat(this.value).toFixed(2);
        }
    });
});

// Auto-refresh dashboard every 5 minutes
if (window.location.pathname === '/dashboard') {
    setTimeout(() => {
        window.location.reload();
    }, 5 * 60 * 1000);
}
