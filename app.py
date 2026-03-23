import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import json
from database import supabase

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard page"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Google Maps Leads - Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            body { font-family: 'Inter', sans-serif; }
            .glass { background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); }
            .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .card-hover { transition: all 0.3s ease; }
            .card-hover:hover { transform: translateY(-2px); box-shadow: 0 10px 40px rgba(0,0,0,0.1); }
            .pulse { animation: pulse 2s infinite; }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
            .fade-in { animation: fadeIn 0.5s ease-in; }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .loading { border: 3px solid #f3f3f3; border-top: 3px solid #667eea; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        </style>
    </head>
    <body class="bg-gray-50 min-h-screen">
        <!-- Header -->
        <header class="gradient-bg text-white shadow-lg">
            <div class="container mx-auto px-4 py-6">
                <div class="flex justify-between items-center">
                    <div class="flex items-center space-x-3">
                        <i class="fas fa-map-marker-alt text-2xl"></i>
                        <h1 class="text-2xl font-bold">Google Maps Leads</h1>
                    </div>
                    <div class="flex items-center space-x-4">
                        <span class="text-sm opacity-80" id="lastUpdate"></span>
                        <button onclick="refreshData()" class="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg transition">
                            <i class="fas fa-sync-alt"></i> Refresh
                        </button>
                    </div>
                </div>
            </div>
        </header>

        <!-- Stats Cards -->
        <div class="container mx-auto px-4 -mt-8">
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                <div class="glass rounded-xl p-6 shadow-lg card-hover">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-500 text-sm font-medium">Total Leads</p>
                            <p class="text-3xl font-bold text-gray-800" id="totalLeads">-</p>
                        </div>
                        <div class="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
                            <i class="fas fa-users text-purple-600 text-xl"></i>
                        </div>
                    </div>
                </div>
                <div class="glass rounded-xl p-6 shadow-lg card-hover">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-500 text-sm font-medium">With Phone</p>
                            <p class="text-3xl font-bold text-gray-800" id="withPhone">-</p>
                        </div>
                        <div class="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
                            <i class="fas fa-phone text-green-600 text-xl"></i>
                        </div>
                    </div>
                </div>
                <div class="glass rounded-xl p-6 shadow-lg card-hover">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-500 text-sm font-medium">With Website</p>
                            <p class="text-3xl font-bold text-gray-800" id="withWebsite">-</p>
                        </div>
                        <div class="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                            <i class="fas fa-globe text-blue-600 text-xl"></i>
                        </div>
                    </div>
                </div>
                <div class="glass rounded-xl p-6 shadow-lg card-hover">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-gray-500 text-sm font-medium">Categories</p>
                            <p class="text-3xl font-bold text-gray-800" id="categories">-</p>
                        </div>
                        <div class="w-12 h-12 bg-orange-100 rounded-full flex items-center justify-center">
                            <i class="fas fa-tags text-orange-600 text-xl"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="container mx-auto px-4">
            <!-- Filters -->
            <div class="glass rounded-xl p-6 shadow-lg mb-8">
                <div class="flex flex-wrap gap-4 items-center">
                    <div class="flex-1 min-w-[200px]">
                        <input type="text" id="searchInput" placeholder="Search businesses..." 
                            class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent">
                    </div>
                    <select id="categoryFilter" class="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500">
                        <option value="">All Categories</option>
                    </select>
                    <select id="hasPhoneFilter" class="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500">
                        <option value="">All</option>
                        <option value="yes">Has Phone</option>
                        <option value="no">No Phone</option>
                    </select>
                    <button onclick="applyFilters()" class="bg-purple-600 hover:bg-purple-700 text-white px-6 py-2 rounded-lg transition">
                        <i class="fas fa-filter"></i> Apply
                    </button>
                </div>
            </div>

            <!-- Results Table -->
            <div class="glass rounded-xl shadow-lg overflow-hidden">
                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Business</th>
                                <th class="px-6 py-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Category</th>
                                <th class="px-6 py-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Address</th>
                                <th class="px-6 py-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Contact</th>
                                <th class="px-6 py-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="leadsTable" class="divide-y divide-gray-100">
                            <tr>
                                <td colspan="5" class="px-6 py-12 text-center">
                                    <div class="loading mx-auto mb-2"></div>
                                    <p class="text-gray-500">Loading leads...</p>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <!-- Pagination -->
                <div class="px-6 py-4 border-t border-gray-100 flex justify-between items-center">
                    <p class="text-sm text-gray-500" id="paginationInfo">Showing 0 results</p>
                    <div class="flex gap-2">
                        <button onclick="prevPage()" id="prevBtn" class="px-4 py-2 border rounded-lg disabled:opacity-50 disabled:cursor-not-allowed">
                            <i class="fas fa-chevron-left"></i>
                        </button>
                        <span class="px-4 py-2" id="pageInfo">1</span>
                        <button onclick="nextPage()" id="nextBtn" class="px-4 py-2 border rounded-lg disabled:opacity-50 disabled:cursor-not-allowed">
                            <i class="fas fa-chevron-right"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let allLeads = [];
            let filteredLeads = [];
            let currentPage = 1;
            const itemsPerPage = 20;

            // Load data on page load
            document.addEventListener('DOMContentLoaded', loadData);

            async function loadData() {
                try {
                    const response = await fetch('/api/leads');
                    const data = await response.json();
                    
                    allLeads = data.leads || [];
                    filteredLeads = [...allLeads];
                    
                    updateStats();
                    populateCategoryFilter();
                    renderTable();
                    updateLastUpdate();
                } catch (error) {
                    console.error('Error loading data:', error);
                    document.getElementById('leadsTable').innerHTML = `
                        <tr>
                            <td colspan="5" class="px-6 py-12 text-center text-red-500">
                                <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                                <p>Error loading data. Please check your Supabase configuration.</p>
                            </td>
                        </tr>
                    `;
                }
            }

            function updateStats() {
                document.getElementById('totalLeads').textContent = allLeads.length;
                document.getElementById('withPhone').textContent = allLeads.filter(l => l.phone).length;
                document.getElementById('withWebsite').textContent = allLeads.filter(l => l.website).length;
                
                const categories = [...new Set(allLeads.map(l => l.category).filter(Boolean))];
                document.getElementById('categories').textContent = categories.length;
            }

            function populateCategoryFilter() {
                const categories = [...new Set(allLeads.map(l => l.category).filter(Boolean))].sort();
                const select = document.getElementById('categoryFilter');
                select.innerHTML = '<option value="">All Categories</option>' + 
                    categories.map(c => `<option value="${c}">${c}</option>`).join('');
            }

            function applyFilters() {
                const search = document.getElementById('searchInput').value.toLowerCase();
                const category = document.getElementById('categoryFilter').value;
                const hasPhone = document.getElementById('hasPhoneFilter').value;

                filteredLeads = allLeads.filter(lead => {
                    const matchSearch = !search || 
                        (lead.name && lead.name.toLowerCase().includes(search)) ||
                        (lead.address && lead.address.toLowerCase().includes(search));
                    const matchCategory = !category || lead.category === category;
                    const matchPhone = !hasPhone || 
                        (hasPhone === 'yes' && lead.phone) || 
                        (hasPhone === 'no' && !lead.phone);
                    return matchSearch && matchCategory && matchPhone;
                });

                currentPage = 1;
                renderTable();
            }

            function renderTable() {
                const start = (currentPage - 1) * itemsPerPage;
                const end = start + itemsPerPage;
                const pageItems = filteredLeads.slice(start, end);

                if (pageItems.length === 0) {
                    document.getElementById('leadsTable').innerHTML = `
                        <tr>
                            <td colspan="5" class="px-6 py-12 text-center text-gray-500">
                                <i class="fas fa-inbox text-2xl mb-2"></i>
                                <p>No leads found</p>
                            </td>
                        </tr>
                    `;
                } else {
                    document.getElementById('leadsTable').innerHTML = pageItems.map(lead => `
                        <tr class="hover:bg-gray-50 fade-in">
                            <td class="px-6 py-4">
                                <div class="font-medium text-gray-900">${lead.name || 'N/A'}</div>
                                ${lead.rating ? `<div class="text-sm text-yellow-500"><i class="fas fa-star"></i> ${lead.rating}</div>` : ''}
                            </td>
                            <td class="px-6 py-4">
                                <span class="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm">${lead.category || 'N/A'}</span>
                            </td>
                            <td class="px-6 py-4 text-gray-600 text-sm">${lead.address || 'N/A'}</td>
                            <td class="px-6 py-4">
                                ${lead.phone ? `<a href="tel:${lead.phone}" class="text-green-600 hover:text-green-700"><i class="fas fa-phone"></i> ${lead.phone}</a>` : '<span class="text-gray-400">-</span>'}
                                ${lead.website ? `<br><a href="${lead.website}" target="_blank" class="text-blue-600 hover:text-blue-700 text-sm"><i class="fas fa-globe"></i> Website</a>` : ''}
                            </td>
                            <td class="px-6 py-4">
                                <button onclick="copyToClipboard('${lead.name || ''}', '${lead.phone || ''}', '${lead.email || ''}')" 
                                    class="text-gray-600 hover:text-purple-600 transition" title="Copy">
                                    <i class="fas fa-copy"></i>
                                </button>
                            </td>
                        </tr>
                    `).join('');
                }

                // Update pagination
                const totalPages = Math.ceil(filteredLeads.length / itemsPerPage);
                document.getElementById('paginationInfo').textContent = 
                    `Showing ${start + 1}-${Math.min(end, filteredLeads.length)} of ${filteredLeads.length}`;
                document.getElementById('pageInfo').textContent = `${currentPage} / ${totalPages}`;
                document.getElementById('prevBtn').disabled = currentPage === 1;
                document.getElementById('nextBtn').disabled = currentPage === totalPages;
            }

            function prevPage() {
                if (currentPage > 1) {
                    currentPage--;
                    renderTable();
                }
            }

            function nextPage() {
                const totalPages = Math.ceil(filteredLeads.length / itemsPerPage);
                if (currentPage < totalPages) {
                    currentPage++;
                    renderTable();
                }
            }

            function refreshData() {
                loadData();
            }

            function copyToClipboard(name, phone, email) {
                const text = `Name: ${name}\nPhone: ${phone}\nEmail: ${email}`;
                navigator.clipboard.writeText(text).then(() => {
                    alert('Copied to clipboard!');
                });
            }

            function updateLastUpdate() {
                const now = new Date();
                document.getElementById('lastUpdate').textContent = 'Updated: ' + now.toLocaleTimeString();
            }

            // Search on Enter key
            document.getElementById('searchInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') applyFilters();
            });
        </script>
    </body>
    </html>
    """
    return html_content

@app.get("/api/leads")
async def get_leads():
    """API endpoint to get all leads from Supabase"""
    if not supabase:
        return {"leads": [], "error": "Supabase not configured"}
    
    try:
        response = supabase.table('leads').select('*').order('timestamp', desc=True).execute()
        return {"leads": response.data}
    except Exception as e:
        return {"leads": [], "error": str(e)}

@app.get("/api/stats")
async def get_stats():
    """API endpoint to get statistics"""
    if not supabase:
        return {"total": 0, "with_phone": 0, "with_website": 0, "categories": 0}
    
    try:
        response = supabase.table('leads').select('*').execute()
        leads = response.data
        
        total = len(leads)
        with_phone = len([l for l in leads if l.get('phone')])
        with_website = len([l for l in leads if l.get('website')])
        categories = len(set([l.get('category') for l in leads if l.get('category')]))
        
        return {
            "total": total,
            "with_phone": with_phone,
            "with_website": with_website,
            "categories": categories
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
