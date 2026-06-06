
// Rest of the functions remain the same...
// (loadCategories, loadItems, changeQty, addToCart, etc.)

// Update checkout to include table number
async function checkout() {
    if (cart.length === 0) {
        showToast('Cart is empty!', '❌');
        return;
    }
    
    const name = prompt('👤 Your name:');
    if (!name) return;
    const phone = prompt('📞 Phone number:');
    if (!phone) return;
    
    // Determine order type based on table number
    let orderType = 'takeaway';
    let address = '';
    
    if (tableNumber === 11) {
        orderType = 'online';
        address = prompt('📍 Delivery address:');
        if (!address) {
            showToast('Address required for delivery!', '❌');
            return;
        }
    } else if (tableNumber && tableNumber >= 1 && tableNumber <= 10) {
        orderType = 'dine_in';
    }
    
    const total = cart.reduce((s, i) => s + i.price * i.quantity, 0);
    const orderData = {
        customer_name: name,
        customer_phone: phone,
        items: cart.map(i => ({ name: i.name, price: i.price, quantity: i.quantity })),
        total_amount: total,
        order_type: orderType,
        notes: address ? `Delivery address: ${address}` : ''
    };
    
    if (tableNumber && tableNumber >= 1 && tableNumber <= 10) {
        orderData.table_number = tableNumber;
    }
    
    try {
        const res = await fetch('/api/table-order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });
        
        const data = await res.json();
        if (data.success) {
            if (tableNumber === 11) {
                showToast(`✅ Order confirmed! #${data.order_number}\nWe will deliver to: ${address}`, '🚚');
            } else if (tableNumber) {
                showToast(`✅ Order confirmed! #${data.order_number} - Table ${tableNumber}`, '🎉');
            } else {
                showToast(`✅ Order confirmed! #${data.order_number}`, '🎉');
            }
            cart = [];
            localStorage.setItem(`cart_table_${tableNumber || 0}`, JSON.stringify(cart));
            updateCartCount();
            closeModal();
        }
    } catch (error) {
        console.error('Error placing order:', error);
        showToast('Error placing order. Please try again.', '❌');
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    updateTableBadge();
    loadTablesGrid();
    loadOnlineQR();
    loadPreview();
    loadCategories();
    updateCartCount();
    initMobileMenu();
    initBackToTop();
    showOrderingInstructions();
    
    window.downloadOnlineQR = downloadOnlineQR;
    window.subscribeNewsletter = subscribeNewsletter;
    
    const cartFab = document.getElementById('cartFab');
    if (cartFab) cartFab.onclick = showCart;
    
    if (tableNumber) {
        console.log(`📱 Table ${tableNumber}${tableNumber === 11 ? ' (Online Order)' : ''} menu loaded`);
    }
});
// Show toast notification
function showToast(message, icon = '✅') {
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.innerHTML = `<i class="fas ${icon === '✅' ? 'fa-check-circle' : 'fa-info-circle'}"></i> ${message}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
}
// frontend/script.js - Replace getTableNumber function
function getTableNumber() {
    // First check URL path (for /table-menu/1)
    const path = window.location.pathname;
    const pathMatch = path.match(/\/table-menu\/(\d+)/);
    if (pathMatch) {
        console.log('Table from path:', pathMatch[1]);
        return parseInt(pathMatch[1]);
    }
    
    // Then check query parameter (for /mobile-menu?table=1)
    const urlParams = new URLSearchParams(window.location.search);
    const tableParam = urlParams.get('table');
    if (tableParam) {
        console.log('Table from query:', tableParam);
        return parseInt(tableParam);
    }
    
    console.log('No table number found');
    return null;
}

const tableNumber = getTableNumber();
console.log('Final table number:', tableNumber);

// Update cart storage key
let cart = JSON.parse(localStorage.getItem(`cart_table_${tableNumber || 0}`) || '[]');
// Update cart count badge
function updateCartCount() {
    const cartCount = document.getElementById('cartCount');
    if (cartCount) {
        const total = cart.reduce((s, i) => s + i.quantity, 0);
        cartCount.textContent = total;
        cartCount.style.display = total > 0 ? 'flex' : 'none';
    }
}

// Load tables grid with QR codes
async function loadTablesGrid() {
    const tablesGrid = document.getElementById('tablesGrid');
    if (!tablesGrid) return;
    
    try {
        const res = await fetch('/api/tables');
        const tables = await res.json();
        
        // Filter only dine-in tables (1-10)
        const dineInTables = tables.filter(t => t.table_number <= 10);
        
        tablesGrid.innerHTML = dineInTables.map(t => `
            <div class="table-card">
                <div class="table-qr">
                    <img src="data:image/png;base64,${t.qr_code}" alt="Table ${t.table_number}">
                </div>
                <div class="table-number">Table ${t.table_number}</div>
                <span class="table-status active"><i class="fas fa-circle"></i> Available</span>
                <div class="table-actions">
                    <button class="btn-download" onclick="downloadTableQR(${t.table_number}, '${t.qr_code}')">
                        <i class="fas fa-download"></i> Download QR
                    </button>
                    <button class="btn-view" onclick="window.open('/table-menu/${t.table_number}', '_blank')">
                        <i class="fas fa-eye"></i> View Menu
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading tables:', error);
    }
}

// Download table QR code
function downloadTableQR(tableNumber, qrCode) {
    const link = document.createElement('a');
    link.download = `table_${tableNumber}_qr.png`;
    link.href = `data:image/png;base64,${qrCode}`;
    link.click();
    showToast(`QR Code for Table ${tableNumber} downloaded!`, '📱');
}

// Load online ordering QR code
async function loadOnlineQR() {
    const container = document.getElementById('onlineQrContainer');
    if (!container) return;
    
    try {
        const res = await fetch('/api/table/11/qr');
        const data = await res.json();
        
        container.innerHTML = `
            <div class="online-qr-wrapper">
                <img src="data:image/png;base64,${data.qr_code}" alt="Online Order QR Code" class="online-qr-img">
                <div class="qr-badges">
                    <span class="badge"><i class="fas fa-mobile-alt"></i> Scan to Order</span>
                    <span class="badge"><i class="fas fa-truck"></i> Delivery Available</span>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading online QR:', error);
        container.innerHTML = '<p class="error">Unable to load QR code. Please refresh the page.</p>';
    }
}

// Download online QR code
async function downloadOnlineQR() {
    try {
        const res = await fetch('/api/table/11/qr');
        const data = await res.json();
        
        const link = document.createElement('a');
        link.download = 'panda_online_order_qr.png';
        link.href = `data:image/png;base64,${data.qr_code}`;
        link.click();
        showToast('Online Order QR Code downloaded!', '📱');
    } catch (error) {
        showToast('Error downloading QR code', '❌');
    }
}

// Load popular dishes preview
async function loadPreview() {
    const previewGrid = document.getElementById('previewGrid');
    if (!previewGrid) return;
    
    try {
        const res = await fetch('/api/menu');
        const items = await res.json();
        const popular = items.slice(0, 8);
        
        previewGrid.innerHTML = popular.map(item => `
            <div class="preview-card">
                <img src="${item.image_url}" class="preview-img" onerror="this.src='https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=300'">
                <div class="preview-info">
                    <div class="preview-name">${item.name}</div>
                    <div class="preview-price">$${item.price}</div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading preview:', error);
    }
}

// Load categories for menu page - UPDATED to match database
async function loadCategories() {
    const categoriesDiv = document.getElementById('categories');
    if (!categoriesDiv) return;
    
    try {
        const res = await fetch('/api/categories');
        const categories = await res.json();
        
        console.log('Categories loaded:', categories); // Debug
        
        if (categories.length === 0) {
            categoriesDiv.innerHTML = '<div class="error">No categories found</div>';
            return;
        }
        
        categoriesDiv.innerHTML = categories.map((c, idx) => `
            <button class="category-tab ${idx === 0 ? 'active' : ''}" onclick="loadItems('${c.key}', this)">
                <i class="fas ${getCategoryIcon(c.key)}"></i> ${c.name}
            </button>
        `).join('');
        
        if (categories.length) {
            loadItems(categories[0].key);
        }
    } catch (error) {
        console.error('Error loading categories:', error);
        categoriesDiv.innerHTML = '<div class="error">Error loading menu. Please refresh the page.</div>';
    }
}

// Get icon for category - UPDATED
function getCategoryIcon(category) {
    const icons = {
        'khmer_noodles': 'fa-utensils',
        'drinks': 'fa-mug-saucer',
        'main_dishes': 'fa-utensil-spoon',
        'rice_dishes': 'fa-bowl-food',
        'desserts': 'fa-ice-cream'
    };
    return icons[category] || 'fa-utensil-spoon';
}

// Load menu items by category with full details
async function loadItems(category, activeBtn = null) {
    const menuDiv = document.getElementById('menuItems');
    if (!menuDiv) return;
    
    menuDiv.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i><p>Loading delicious food...</p></div>';
    
    try {
        const res = await fetch(`/api/menu?category=${category}`);
        const items = await res.json();
        
        console.log(`Items loaded for ${category}:`, items.length); // Debug
        
        if (items.length === 0) {
            menuDiv.innerHTML = '<div class="loading-spinner"><i class="fas fa-sad-tear"></i><p>No items in this category</p><p style="font-size:0.8rem">Please check back later!</p></div>';
            return;
        }
        
        menuDiv.innerHTML = items.map(item => `
            <div class="menu-card-modern">
                <div class="menu-badge">⏱️ ${item.preparation_time || 10} min</div>
                <img src="${item.image_url}" class="menu-img-modern" onerror="this.src='https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=300'">
                <div class="menu-info-modern">
                    <div class="menu-name-modern">${item.name}</div>
                    <div class="menu-name-kh">${item.name_kh || ''}</div>
                    <div class="menu-price-modern">$${item.price}</div>
                    <div class="menu-description">${item.description || 'Delicious Cambodian dish'}</div>
                    <div class="prep-time">
                        <i class="fas fa-clock"></i> Preparation: ${item.preparation_time || 10} minutes
                    </div>
                    <div class="quantity-control">
                        <span class="quantity-label">Quantity:</span>
                        <div class="quantity-buttons">
                            <button class="qty-btn" onclick="changeQty('${item.name.replace(/'/g, "\\'")}', ${item.price}, -1)">-</button>
                            <span class="qty-value" id="qty_${item.id}">${getItemQty(item.name)}</span>
                            <button class="qty-btn" onclick="changeQty('${item.name.replace(/'/g, "\\'")}', ${item.price}, 1)">+</button>
                        </div>
                    </div>
                    <button class="add-to-cart" onclick="addToCart('${item.name.replace(/'/g, "\\'")}', ${item.price})">
                        <i class="fas fa-cart-plus"></i> Add to Cart
                    </button>
                </div>
            </div>
        `).join('');
        
        // Update active tab
        if (activeBtn) {
            document.querySelectorAll('.category-tab').forEach(btn => btn.classList.remove('active'));
            activeBtn.classList.add('active');
        }
    } catch (error) {
        console.error('Error loading items:', error);
        menuDiv.innerHTML = '<div class="loading-spinner"><i class="fas fa-exclamation-triangle"></i><p>Error loading menu. Please refresh the page.</p></div>';
    }
}

function getItemQty(name) {
    const item = cart.find(i => i.name === name);
    return item ? item.quantity : 0;
}

function changeQty(name, price, delta) {
    let item = cart.find(i => i.name === name);
    if (item) {
        item.quantity += delta;
        if (item.quantity <= 0) {
            cart = cart.filter(i => i.name !== name);
        }
    } else if (delta > 0) {
        cart.push({ name, price, quantity: 1 });
    }
    
    localStorage.setItem(`cart_table_${tableNumber || 0}`, JSON.stringify(cart));
    updateCartCount();
    
    // Refresh current view - update quantity display
    const activeTab = document.querySelector('.category-tab.active');
    if (activeTab) {
        const onclickAttr = activeTab.getAttribute('onclick');
        if (onclickAttr) {
            const match = onclickAttr.match(/'([^']+)'/);
            if (match) {
                loadItems(match[1]);
            }
        }
    }
}

function addToCart(name, price) {
    changeQty(name, price, 1);
    showToast(`Added ${name} to cart`, '🛒');
}

// Show cart modal
function showCart() {
    const modal = document.getElementById('cartModal');
    const cartDiv = document.getElementById('cartItems');
    const totalDiv = document.getElementById('cartTotal');
    
    if (!modal) return;
    
    if (cart.length === 0) {
        cartDiv.innerHTML = '<div class="loading-spinner"><p>🛒 Your cart is empty</p><p style="font-size:0.8rem">Add some delicious food!</p></div>';
        totalDiv.innerHTML = '';
    } else {
        let total = 0;
        cartDiv.innerHTML = cart.map((item, idx) => {
            total += item.price * item.quantity;
            return `
                <div class="cart-item-modern">
                    <div class="cart-item-info">
                        <div class="cart-item-name">${item.name}</div>
                        <div class="cart-item-price">$${item.price} x ${item.quantity} = $${(item.price * item.quantity).toFixed(2)}</div>
                    </div>
                    <button class="cart-item-remove" onclick="removeFromCart(${idx})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
        }).join('');
        totalDiv.innerHTML = `Total: <span style="color: var(--secondary); font-size: 1.3rem;">$${total.toFixed(2)}</span>`;
    }
    modal.style.display = 'flex';
}

function removeFromCart(idx) {
    cart.splice(idx, 1);
    localStorage.setItem(`cart_table_${tableNumber || 0}`, JSON.stringify(cart));
    updateCartCount();
    showCart();
}

function closeModal() {
    const modal = document.getElementById('cartModal');
    if (modal) modal.style.display = 'none';
}

// Checkout - Updated for online orders
async function checkout() {
    if (cart.length === 0) {
        showToast('Cart is empty!', '❌');
        return;
    }
    
    const name = prompt('👤 Your name:');
    if (!name) return;
    const phone = prompt('📞 Phone number:');
    if (!phone) return;
    
    // Ask for address if online order (table 11)
    let address = '';
    let orderType = 'dine_in';
    
    if (tableNumber === 11) {
        orderType = 'online';
        address = prompt('📍 Delivery address:');
        if (!address) {
            showToast('Address required for delivery!', '❌');
            return;
        }
    } else if (tableNumber) {
        orderType = 'dine_in';
    } else {
        orderType = 'pickup';
    }
    
    const total = cart.reduce((s, i) => s + i.price * i.quantity, 0);
    const orderData = {
        customer_name: name,
        customer_phone: phone,
        items: cart,
        total_amount: total,
        order_type: orderType,
        notes: address ? `Delivery address: ${address}` : ''
    };
    
    if (tableNumber && tableNumber !== 11) {
        orderData.table_number = tableNumber;
    }
    
    try {
        const res = await fetch('/api/table-order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });
        
        const data = await res.json();
        if (data.success) {
            if (tableNumber === 11) {
                showToast(`✅ Order confirmed! #${data.order_number}\nWe will deliver to: ${address}`, '🚚');
            } else {
                showToast(`✅ Order confirmed! #${data.order_number}`, '🎉');
            }
            cart = [];
            localStorage.setItem(`cart_table_${tableNumber || 0}`, JSON.stringify(cart));
            updateCartCount();
            closeModal();
        }
    } catch (error) {
        console.error('Error placing order:', error);
        showToast('Error placing order. Please try again.', '❌');
    }
}

// Update table badge on menu page
function updateTableBadge() {
    const badge = document.getElementById('tableBadge');
    if (badge && tableNumber) {
        if (tableNumber === 11) {
            badge.innerHTML = `<i class="fas fa-shopping-bag"></i> Online Order / Takeaway <i class="fas fa-qrcode"></i>`;
        } else {
            badge.innerHTML = `<i class="fas fa-chair"></i> Table ${tableNumber} <i class="fas fa-qrcode"></i>`;
        }
    }
}

// Newsletter subscription
function subscribeNewsletter(event) {
    event.preventDefault();
    const email = event.target.querySelector('input[type="email"]').value;
    
    if (email) {
        showToast(`Thanks for subscribing! We'll send updates to ${email}`, '📧');
        event.target.reset();
    }
}

// Mobile menu toggle
function initMobileMenu() {
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const mobileMenu = document.getElementById('mobileMenu');
    
    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenu.classList.toggle('active');
        });
        
        document.addEventListener('click', (e) => {
            if (mobileMenu.classList.contains('active') && 
                !mobileMenu.contains(e.target) && 
                !mobileMenuBtn.contains(e.target)) {
                mobileMenu.classList.remove('active');
            }
        });
    }
}

// Back to top button
function initBackToTop() {
    const backToTop = document.getElementById('backToTop');
    if (backToTop) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 300) {
                backToTop.classList.add('show');
            } else {
                backToTop.classList.remove('show');
            }
        });
        
        backToTop.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
}


// Initialize everything
document.addEventListener('DOMContentLoaded', () => {
    updateTableBadge();
    loadTablesGrid();
    loadOnlineQR();
    loadPreview();
    loadCategories();
    updateCartCount();
    initMobileMenu();
    initBackToTop();
    
    // Make downloadOnlineQR available globally
    window.downloadOnlineQR = downloadOnlineQR;
    window.subscribeNewsletter = subscribeNewsletter;
    
    // Cart button
    const cartFab = document.getElementById('cartFab');
    if (cartFab) cartFab.onclick = showCart;
    
    // Log table info
    if (tableNumber) {
        console.log(`📱 Table ${tableNumber}${tableNumber === 11 ? ' (Online Order)' : ''} menu loaded`);
    }
});