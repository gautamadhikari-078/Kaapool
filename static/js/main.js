/**
 * KAAPOOL MAIN JAVASCRIPT (INTERACTIVE UI HANDLERS)
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. FAQ Accordion Handler
    const faqItems = document.querySelectorAll('.faq-item');
    faqItems.forEach(item => {
        const questionBtn = item.querySelector('.faq-question');
        if (questionBtn) {
            questionBtn.addEventListener('click', () => {
                const isActive = item.classList.contains('active');
                
                // Close all other items
                faqItems.forEach(otherItem => otherItem.classList.remove('active'));
                
                // Toggle clicked item
                if (!isActive) {
                    item.classList.add('active');
                }
            });
        }
    });

    // 2. Search Card Tab Switcher
    const searchTabs = document.querySelectorAll('.search-tab');
    const searchForm = document.querySelector('.search-form-grid');
    const submitBtn = document.querySelector('.btn-search-submit');

    searchTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            searchTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            const mode = tab.getAttribute('data-type');
            if (mode === 'offer') {
                if (submitBtn) {
                    submitBtn.innerHTML = 'Publish Ride <i class="fa-solid fa-plus"></i>';
                }
                if (searchForm) {
                    searchForm.setAttribute('action', '/rides/create/');
                }
            } else {
                if (submitBtn) {
                    submitBtn.innerHTML = 'Search <i class="fa-solid fa-magnifying-glass"></i>';
                }
                if (searchForm) {
                    searchForm.setAttribute('action', '/rides/search/');
                }
            }
        });
    });

    console.log('Kaapool interactive UI components initialized.');
});
