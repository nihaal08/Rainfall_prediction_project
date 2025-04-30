document.addEventListener('DOMContentLoaded', () => {
    // Smooth scroll for nav links
    document.querySelectorAll('.nav-links a').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const url = this.getAttribute('href');
            window.location.href = url;
        });
    });

    // Form submission loading state
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', (e) => {
            const submitBtn = form.querySelector('.btn');
            submitBtn.disabled = true;
            submitBtn.innerText = 'Processing...';
            // Reset button state if submission fails
            setTimeout(() => {
                submitBtn.disabled = false;
                submitBtn.innerText = 'Login';
            }, 2000);
        });
    });

    // Auto-dismiss flash messages
    setTimeout(() => {
        document.querySelectorAll('.alert').forEach(alert => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        });
    }, 3000);

    // Remove incorrect session check
    // fetch('/check_session').then(response => {
    //     if (!response.ok) {
    //         window.location.href = '/login';
    //     }
    // });

    // Show prediction modal if present
    const modal = document.getElementById('predictionModal');
    if (modal) {
        modal.style.display = 'flex';
    }
});

// Close modal function
function closeModal() {
    const modal = document.getElementById('predictionModal');
    if (modal) {
        modal.style.display = 'none';
    }
}