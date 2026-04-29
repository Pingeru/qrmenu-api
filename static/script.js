// This assumes 'backendData' is defined globally in the HTML
const categoryView = document.getElementById('category-view');
const productView = document.getElementById('product-view');
const backBtn = document.getElementById('back-btn');

function renderCategories() {
    categoryView.innerHTML = '';
    backendData.categories.forEach(category => {
        const card = document.createElement('div');
        card.className = 'card';
        card.onclick = () => showProducts(category.id);
        card.innerHTML = `
            <img src="${category.image}" alt="${category.name}">
            <div class="card-content">
                <h3 class="card-title">${category.name}</h3>
            </div>
        `;
        categoryView.appendChild(card);
    });
}

function showProducts(categoryId) {
    categoryView.style.display = 'none';
    productView.style.display = 'grid';
    backBtn.style.display = 'inline-block';
    
    productView.innerHTML = '';
    const products = backendData.products[categoryId] || [];

    if (products.length === 0) {
        productView.innerHTML = '<p>No products available in this category.</p>';
        return;
    }

    products.forEach(product => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <img src="${product.image}" alt="${product.name}">
            <div class="card-content">
                <h3 class="card-title">${product.name}</h3>
                <p class="product-price">${product.price}</p>
                <p class="product-desc">${product.description}</p>
            </div>
        `;
        productView.appendChild(card);
    });
}

function showCategories() {
    categoryView.style.display = 'grid';
    productView.style.display = 'none';
    backBtn.style.display = 'none';
}

// Initialize the app
renderCategories();