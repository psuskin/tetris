"""
3D visualization system using Plotly with proper z-buffering and perspective.

This replaces matplotlib with Plotly for TRUE 3D rendering without bleeding artifacts.
"""

import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder
import numpy as np
import re
from typing import List, Optional

from product import Product, ProductType
from container import RollContainer
from packing_algorithm import PackingConfiguration, PlacedProduct


class PackingVisualizerPlotly:
    """Interactive 3D visualization with PROPER depth handling using Plotly."""
    
    def __init__(self, config: PackingConfiguration):
        self.config = config
        self.current_step = 0
        
        # Color palette
        self.color_palette = [
            'rgb(31, 119, 180)', 'rgb(255, 127, 14)', 'rgb(44, 160, 44)',
            'rgb(214, 39, 40)', 'rgb(148, 103, 189)', 'rgb(140, 86, 75)',
            'rgb(227, 119, 194)', 'rgb(127, 127, 127)', 'rgb(188, 189, 34)',
            'rgb(23, 190, 207)'
        ]
        self.product_colors = {}
    
    def _darken_color(self, rgb_color: str) -> str:
        """Darken an RGB color for edges."""
        match = re.match(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', rgb_color)
        if match:
            r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
            # Darken by 40%
            r, g, b = int(r * 0.6), int(g * 0.6), int(b * 0.6)
            return f'rgb({r}, {g}, {b})'
        return rgb_color  # Fallback
    
    def get_product_color(self, product: Product) -> str:
        """Get or assign a color for a product."""
        if product.color:
            # Convert matplotlib color names to rgb
            color_map = {
                'lightblue': 'rgb(173, 216, 230)',
                'lightcoral': 'rgb(240, 128, 128)',
                'lightgreen': 'rgb(144, 238, 144)',
                'lightyellow': 'rgb(255, 255, 224)',
                'lightgray': 'rgb(211, 211, 211)',
                'lightcyan': 'rgb(224, 255, 255)',
                'skyblue': 'rgb(135, 206, 235)',
                'deepskyblue': 'rgb(0, 191, 255)',
                'paleturquoise': 'rgb(175, 238, 238)',
                'tan': 'rgb(210, 180, 140)',
                'wheat': 'rgb(245, 222, 179)',
                'burlywood': 'rgb(222, 184, 135)',
                'beige': 'rgb(245, 245, 220)',
                'ivory': 'rgb(255, 255, 240)',
                'gold': 'rgb(255, 215, 0)',
                'yellow': 'rgb(255, 255, 0)',
                'blue': 'rgb(0, 0, 255)',
                'red': 'rgb(255, 0, 0)',
                'green': 'rgb(0, 128, 0)',
                'darkgreen': 'rgb(0, 100, 0)',
                'limegreen': 'rgb(50, 205, 50)',
                'olive': 'rgb(128, 128, 0)',
                'orange': 'rgb(255, 165, 0)',
                'purple': 'rgb(128, 0, 128)',
                'brown': 'rgb(139, 69, 19)',
                'chocolate': 'rgb(210, 105, 30)',
                'maroon': 'rgb(128, 0, 0)',
                'darkred': 'rgb(139, 0, 0)',
                'lavender': 'rgb(230, 230, 250)',
                'white': 'rgb(245, 245, 245)',
            }
            return color_map.get(product.color, product.color)
        
        if product.id not in self.product_colors:
            color_idx = len(self.product_colors) % len(self.color_palette)
            self.product_colors[product.id] = self.color_palette[color_idx]
        
        return self.product_colors[product.id]
    
    def create_cylinder_mesh(self, position: tuple, dimensions: tuple, 
                            orientation: str, color: str, opacity: float = 0.7, 
                            name: str = "", edge_color: str = None) -> go.Mesh3d:
        """Create a 3D cylinder mesh."""
        x, y, z = position
        d1, d2, h = dimensions  # For M orientation: (height, diameter, diameter) - height becomes length
        
        # Check if lying on side (M orientation)
        if orientation == 'M':
            # Lying on side: d1 is the original height (now length along x), d2 is diameter
            length = d1  # The original height becomes the length
            radius = d2 / 2  # d2 is the diameter
            
            # Create cylinder along x-axis
            theta = np.linspace(0, 2*np.pi, 20)
            x_cyl = np.linspace(x, x + length, 10)
            theta_grid, x_grid = np.meshgrid(theta, x_cyl)
            y_grid = y + radius + radius * np.cos(theta_grid)
            z_grid = z + radius + radius * np.sin(theta_grid)
            
        else:
            # Standing upright: d1 is diameter (radius), h is height along z-axis
            radius = d1 / 2
            theta = np.linspace(0, 2*np.pi, 20)
            z_cyl = np.linspace(z, z + h, 10)
            theta_grid, z_grid = np.meshgrid(theta, z_cyl)
            x_grid = x + radius + radius * np.cos(theta_grid)
            y_grid = y + radius + radius * np.sin(theta_grid)
        
        # Flatten for Mesh3d
        x_flat = x_grid.flatten()
        y_flat = y_grid.flatten()
        z_flat = z_grid.flatten()
        
        # Create triangulation
        n_theta = 20
        n_z = 10
        i, j, k = [], [], []
        for ti in range(n_z - 1):
            for tj in range(n_theta - 1):
                idx = ti * n_theta + tj
                # First triangle
                i.append(idx)
                j.append(idx + 1)
                k.append(idx + n_theta)
                # Second triangle
                i.append(idx + 1)
                j.append(idx + n_theta + 1)
                k.append(idx + n_theta)
        
        return go.Mesh3d(
            x=x_flat, y=y_flat, z=z_flat,
            i=i, j=j, k=k,
            color=color,
            opacity=opacity,
            name=name,
            showlegend=False,
            hoverinfo='text',
            text=name,
            flatshading=False,
            lighting=dict(ambient=0.6, diffuse=0.8, specular=0.2, roughness=0.5),
            lightposition=dict(x=100, y=100, z=200),
            contour=dict(
                show=True,
                color='black',
                width=3
            )
        )
    
    def create_box_mesh(self, position: tuple, dimensions: tuple, color: str, 
                       opacity: float = 0.7, name: str = "", edge_color: str = None) -> go.Mesh3d:
        """Create a 3D box mesh with proper faces."""
        x, y, z = position
        l, w, h = dimensions
        
        # 8 vertices of the box
        vertices = np.array([
            [x, y, z],          # 0
            [x+l, y, z],        # 1
            [x+l, y+w, z],      # 2
            [x, y+w, z],        # 3
            [x, y, z+h],        # 4
            [x+l, y, z+h],      # 5
            [x+l, y+w, z+h],    # 6
            [x, y+w, z+h],      # 7
        ])
        
        # Triangular faces (2 triangles per face = 12 triangles total)
        i = [0, 0, 1, 1, 2, 2, 3, 3, 0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
        j = [1, 3, 2, 0, 3, 1, 0, 2, 4, 1, 5, 0, 3, 4, 5, 2, 6, 3, 7, 0, 5, 7, 6, 4]
        k = [2, 2, 3, 3, 0, 0, 1, 1, 5, 5, 1, 1, 7, 7, 2, 2, 3, 3, 4, 4, 6, 6, 7, 7]
        
        return go.Mesh3d(
            x=vertices[:, 0],
            y=vertices[:, 1],
            z=vertices[:, 2],
            i=i, j=j, k=k,
            color=color,
            opacity=opacity,
            name=name,
            showlegend=False,
            hoverinfo='text',
            text=name,
            flatshading=False,
            lighting=dict(ambient=0.6, diffuse=0.8, specular=0.2, roughness=0.5),
            lightposition=dict(x=100, y=100, z=200),
            contour=dict(
                show=True,
                color=edge_color if edge_color else color,
                width=6
            )
        )
    
    def create_fragile_grid(self, position: tuple, dimensions: tuple) -> List[go.Scatter3d]:
        """Create simple red X pattern on fragile items - performance optimized."""
        x, y, z = position
        l, w, h = dimensions
        
        z_top = z + h + 0.01  # Slightly above surface
        
        grid_lines = []
        
        # Simple X pattern: 4 lines from corners
        # Diagonal 1: bottom-left to top-right
        grid_lines.append(go.Scatter3d(
            x=[x, x + l, None],
            y=[y, y + w, None],
            z=[z_top, z_top, None],
            mode='lines',
            line=dict(color='darkred', width=4),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Diagonal 2: bottom-right to top-left
        grid_lines.append(go.Scatter3d(
            x=[x + l, x, None],
            y=[y, y + w, None],
            z=[z_top, z_top, None],
            mode='lines',
            line=dict(color='darkred', width=4),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        return grid_lines

    
    def create_container_traces(self, current_step: int = -1) -> List:
        """Create container boundary and shelf traces.
        
        Args:
            current_step: Current step index (-1 for all steps). Shelves are colored
                         brown only at heights where products are placed DIRECTLY on shelves.
        """
        container = self.config.container
        traces = []
        
        # Determine which shelf levels have products placed DIRECTLY on them
        # (not products stacked on other products that happen to be at shelf height)
        used_shelf_levels = set()
        if current_step >= 0:
            for i in range(current_step + 1):
                placed = self.config.placed_products[i]
                z = placed.position[2]
                # Only consider shelf levels (multiples of 20cm, excluding floor)
                if z > 0 and z % 20 == 0:
                    # Check if this is ACTUALLY on a shelf (not stacked on another product)
                    # A product is on a shelf if there's no other product directly below it
                    is_on_shelf = True
                    for j in range(i):
                        other = self.config.placed_products[j]
                        other_top = other.position[2] + other.dimensions[2]
                        # If another product's top is at this product's bottom, it's stacked
                        if abs(other_top - z) < 0.1:
                            # Check if they overlap in x,y
                            x_overlap = (placed.position[0] < other.position[0] + other.dimensions[0] and
                                       placed.position[0] + placed.dimensions[0] > other.position[0])
                            y_overlap = (placed.position[1] < other.position[1] + other.dimensions[1] and
                                       placed.position[1] + placed.dimensions[1] > other.position[1])
                            if x_overlap and y_overlap:
                                is_on_shelf = False
                                break
                    
                    if is_on_shelf:
                        used_shelf_levels.add(int(z))
        
        # Container box (very transparent)
        container_mesh = self.create_box_mesh(
            (0, 0, 0),
            (container.length, container.width, container.height),
            'rgb(200, 200, 200)',
            opacity=0.03,
            name="Container"
        )
        traces.append(container_mesh)
        
        # Container edges (single optimized trace)
        x_coords = [0, container.length, container.length, 0, 0, None,
                    0, 0, None, container.length, container.length, None,
                    container.length, container.length, None, 0, 0]
        y_coords = [0, 0, container.width, container.width, 0, None,
                    0, 0, None, 0, 0, None,
                    container.width, container.width, None, container.width, container.width]
        z_coords = [0, 0, 0, 0, 0, None,
                    0, container.height, None, 0, container.height, None,
                    0, container.height, None, 0, container.height]
        
        traces.append(go.Scatter3d(
            x=x_coords, y=y_coords, z=z_coords,
            mode='lines',
            line=dict(color='gray', width=1),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Draw shelf floors every 20cm — only INSTALLED (used) shelves get a
        # filled surface. Unused shelf positions only show a faint dashed outline
        # so that stacked products don't appear to clip through a shelf.
        for z in range(20, int(container.height), 20):
            if z in used_shelf_levels:
                # Real installed shelf — brown filled surface
                traces.append(go.Mesh3d(
                    x=[0, container.length, container.length, 0],
                    y=[0, 0, container.width, container.width],
                    z=[z, z, z, z],
                    i=[0, 0], j=[1, 2], k=[2, 3],
                    color='rgb(139, 90, 43)',
                    opacity=0.4,
                    showlegend=False,
                    hoverinfo='skip'
                ))
                # Solid edge for installed shelf
                traces.append(go.Scatter3d(
                    x=[0, container.length, container.length, 0, 0],
                    y=[0, 0, container.width, container.width, 0],
                    z=[z, z, z, z, z],
                    mode='lines',
                    line=dict(color='rgb(139, 90, 43)', width=2),
                    showlegend=False,
                    hoverinfo='skip'
                ))
            else:
                # Unused shelf position — faint dashed outline only, no surface
                traces.append(go.Scatter3d(
                    x=[0, container.length, container.length, 0, 0],
                    y=[0, 0, container.width, container.width, 0],
                    z=[z, z, z, z, z],
                    mode='lines',
                    line=dict(color='lightgray', width=1, dash='dash'),
                    showlegend=False,
                    hoverinfo='skip'
                ))
            
            # Height label
            traces.append(go.Scatter3d(
                x=[container.length + 5],
                y=[container.width / 2],
                z=[z],
                mode='text',
                text=[f'{z}cm'],
                textfont=dict(size=10, color='gray'),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        return traces
    
    def _create_step_data(self, step_idx):
        """Create data for a specific step (container + products up to step)."""
        traces = []
        
        # Add container with shelves colored based on usage
        traces.extend(self.create_container_traces(current_step=step_idx))
        
        # Add all products up to this step
        for i in range(step_idx + 1):
            placed = self.config.placed_products[i]
            
            # Determine color and opacity
            color = self.get_product_color(placed.product)
            if placed.product.fragile:
                color = 'rgb(240, 128, 128)'
            
            opacity = 0.9 if i == step_idx else 0.65
            
            # Add product (box or cylinder)
            product_name = f"{placed.product.id} - {placed.product.name}"
            if placed.product.fragile:
                product_name = f"🔴 {product_name}"
            
            # Check if cylinder or box
            if placed.product.product_type == ProductType.CYLINDER:
                # Create cylinder
                # Darker edge color
                edge_color = self._darken_color(color)
                cylinder_mesh = self.create_cylinder_mesh(
                    placed.position,
                    placed.dimensions,
                    placed.orientation,
                    color,
                    opacity=opacity,
                    name=product_name,
                    edge_color=edge_color
                )
                traces.append(cylinder_mesh)
            else:
                # Create box with darker edges
                edge_color = self._darken_color(color)
                box_mesh = self.create_box_mesh(
                    placed.position,
                    placed.dimensions,
                    color,
                    opacity=opacity,
                    name=product_name,
                    edge_color=edge_color
                )
                traces.append(box_mesh)
                
                # Skip individual edges - mesh contours handle edges efficiently
            
            # Add fragile grid if needed (simplified)
            if placed.product.fragile:
                grid = self.create_fragile_grid(placed.position, placed.dimensions)
                traces.extend(grid)
        
        return traces
    
    def show(self, start_step: int = 0):
        """Display step-by-step visualization with efficient rendering."""
        # Pre-generate all step data
        all_step_data = []
        for step_idx in range(len(self.config.placed_products)):
            step_data = self._create_step_data(step_idx)
            all_step_data.append(step_data)
        
        # Create initial figure with starting step
        fig = go.Figure(data=all_step_data[start_step])
        
        # Create dropdown menu items - use restyle to trigger updates
        dropdown_buttons = []
        for step_idx in range(len(self.config.placed_products)):
            product = self.config.placed_products[step_idx]
            label = f"Step {step_idx + 1}: {product.product.name}"
            if product.product.fragile:
                label = f"🔴 {label}"
            
            # Use restyle with a dummy property to trigger event with step index
            dropdown_buttons.append({
                'label': label,
                'method': 'restyle',
                'args': [{'_stepIndex': step_idx}]
            })
        
        # Set up initial title
        initial_product = self.config.placed_products[start_step]
        initial_title = f"Step {start_step + 1}/{len(self.config.placed_products)}: {initial_product.product.name}"
        if initial_product.product.fragile:
            initial_title = f"🔴 {initial_title}"
        
        # Layout
        fig.update_layout(
            title=initial_title,
            scene=dict(
                xaxis=dict(title='Length (cm)', range=[0, self.config.container.length * 1.1]),
                yaxis=dict(title='Width (cm)', range=[0, self.config.container.width * 1.1]),
                zaxis=dict(title='Height (cm)', range=[0, self.config.container.height * 1.05]),
                aspectmode='manual',
                aspectratio=dict(
                    x=self.config.container.length / self.config.container.height,
                    y=self.config.container.width / self.config.container.height,
                    z=1.0
                ),
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.2),
                    center=dict(x=0, y=0, z=0),
                    up=dict(x=0, y=0, z=1)
                )
            ),
            showlegend=False,
            height=900,
            margin=dict(l=250, r=250, t=150, b=100),
            updatemenus=[
                {
                    'buttons': dropdown_buttons,
                    'direction': 'down',
                    'showactive': True,
                    'x': 0.01,
                    'xanchor': 'left',
                    'y': 1.0,
                    'yanchor': 'top',
                    'bgcolor': 'lightgray',
                    'bordercolor': 'gray',
                    'borderwidth': 1
                }
            ]
        )
        
        # Generate HTML with custom navigation buttons
        html_template = """
        <html>
        <head>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
                #plotDiv {{ width: 100%; height: calc(100vh - 70px); }}
                #controls {{ 
                    position: fixed; 
                    bottom: 0; 
                    left: 0; 
                    right: 0; 
                    height: 70px;
                    background: #f5f5f5; 
                    border-top: 2px solid #ccc;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 20px;
                    padding: 0 20px;
                }}
                button {{
                    padding: 10px 25px;
                    font-size: 16px;
                    font-weight: bold;
                    border: 2px solid #333;
                    border-radius: 5px;
                    background: white;
                    cursor: pointer;
                    transition: all 0.2s;
                }}
                button:hover {{ background: #e0e0e0; }}
                button:active {{ transform: scale(0.95); }}
                button:disabled {{ 
                    opacity: 0.3; 
                    cursor: not-allowed;
                    background: #f0f0f0;
                }}
                #stepInfo {{
                    font-size: 16px;
                    font-weight: bold;
                    color: #333;
                    min-width: 150px;
                    text-align: center;
                }}
                .hint {{
                    font-size: 12px;
                    color: #666;
                    font-style: italic;
                }}
            </style>
        </head>
        <body>
            <div id="plotDiv"></div>
            <div id="controls">
                <button id="prevBtn" onclick="previousStep()">◀ Previous</button>
                <div id="stepInfo">Step <span id="currentStep">1</span> of {total_steps}</div>
                <button id="nextBtn" onclick="nextStep()">Next ▶</button>
                <span class="hint">Keyboard: ← → or use dropdown above</span>
            </div>
            
            <script>
                let currentStep = {start_step};
                const totalSteps = {total_steps};
                const allStepData = {all_step_data_json};
                const stepTitles = {step_titles_json};
                
                const layout = {layout_json};
                const config = {{responsive: true}};
                
                Plotly.newPlot('plotDiv', allStepData[currentStep], layout, config);
                
                // Handle dropdown selection via restyle event
                const plotDiv = document.getElementById('plotDiv');
                plotDiv.on('plotly_restyle', function(data) {{
                    // data is array: [updateObj, traceIndices]
                    if (data && data[0] && typeof data[0]._stepIndex === 'number') {{
                        const newStep = data[0]._stepIndex;
                        if (newStep >= 0 && newStep < totalSteps) {{
                            updateStep(newStep);
                        }}
                    }}
                }});
                
                function updateStep(newStep) {{
                    if (newStep < 0 || newStep >= totalSteps) return;
                    currentStep = newStep;
                    
                    Plotly.react('plotDiv', allStepData[currentStep], {{
                        ...layout,
                        title: stepTitles[currentStep]
                    }}, config);
                    
                    document.getElementById('currentStep').textContent = currentStep + 1;
                    document.getElementById('prevBtn').disabled = (currentStep === 0);
                    document.getElementById('nextBtn').disabled = (currentStep === totalSteps - 1);
                }}
                
                function previousStep() {{
                    updateStep(currentStep - 1);
                }}
                
                function nextStep() {{
                    updateStep(currentStep + 1);
                }}
                
                // Keyboard navigation
                document.addEventListener('keydown', (e) => {{
                    if (e.key === 'ArrowLeft') {{
                        previousStep();
                    }} else if (e.key === 'ArrowRight') {{
                        nextStep();
                    }}
                }});
                
                // Initialize button states
                updateStep(currentStep);
            </script>
        </body>
        </html>
        """
        
        # Prepare data for JSON serialization
        import json
        
        # Custom JSON encoder for numpy arrays
        class NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.floating):
                    return float(obj)
                return super().default(obj)
        
        # Convert Plotly traces to dictionaries
        all_step_data_dicts = []
        for step_data in all_step_data:
            step_dicts = []
            for trace in step_data:
                step_dicts.append(trace.to_plotly_json())
            all_step_data_dicts.append(step_dicts)
        
        all_step_data_json = json.dumps(all_step_data_dicts, cls=NumpyEncoder)
        step_titles = [f"Step {i+1}/{len(self.config.placed_products)}: {self.config.placed_products[i].product.name}" 
                      for i in range(len(self.config.placed_products))]
        step_titles_json = json.dumps(step_titles)
        
        layout_dict = {
            'title': initial_title,
            'scene': {
                'xaxis': {'title': 'Length (cm)', 'range': [0, self.config.container.length * 1.1]},
                'yaxis': {'title': 'Width (cm)', 'range': [0, self.config.container.width * 1.1]},
                'zaxis': {'title': 'Height (cm)', 'range': [0, self.config.container.height * 1.05]},
                'aspectmode': 'manual',
                'aspectratio': {
                    'x': self.config.container.length / self.config.container.height,
                    'y': self.config.container.width / self.config.container.height,
                    'z': 1.0
                },
                'camera': {
                    'eye': {'x': 1.5, 'y': 1.5, 'z': 1.2},
                    'center': {'x': 0, 'y': 0, 'z': 0},
                    'up': {'x': 0, 'y': 0, 'z': 1}
                }
            },
            'showlegend': False,
            'height': 900,
            'margin': {'l': 250, 'r': 250, 't': 150, 'b': 100},
            'updatemenus': [{
                'buttons': dropdown_buttons,
                'direction': 'down',
                'showactive': True,
                'x': 0.01,
                'xanchor': 'left',
                'y': 1.0,
                'yanchor': 'top',
                'bgcolor': 'lightgray',
                'bordercolor': 'gray',
                'borderwidth': 1
            }]
        }
        layout_json = json.dumps(layout_dict)
        
        html_content = html_template.format(
            total_steps=len(self.config.placed_products),
            start_step=start_step,
            all_step_data_json=all_step_data_json,
            step_titles_json=step_titles_json,
            layout_json=layout_json
        )
        
        # Save and open HTML file
        import tempfile
        import webbrowser
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            html_path = f.name
        
        webbrowser.open('file://' + os.path.abspath(html_path))
        print(f"\n✓ Visualization opened in browser with Previous/Next buttons")
        print(f"  Controls: ◀ Previous | Next ▶ buttons OR ← → arrow keys")
    
    def show_all(self):
        """Display all products at once."""
        fig = go.Figure()
        
        # Add container
        for trace in self.create_container_traces():
            fig.add_trace(trace)
        
        # Add all products
        for placed in self.config.placed_products:
            color = self.get_product_color(placed.product)
            if placed.product.fragile:
                color = 'rgb(240, 128, 128)'
            
            product_name = f"{placed.product.id} - {placed.product.name}"
            if placed.product.fragile:
                product_name = f"🔴 {product_name}"
            
            edge_color = self._darken_color(color)
            
            if placed.product.product_type == ProductType.CYLINDER:
                fig.add_trace(self.create_cylinder_mesh(
                    placed.position, placed.dimensions, placed.orientation,
                    color, opacity=0.7, name=product_name, edge_color=edge_color
                ))
            else:
                fig.add_trace(self.create_box_mesh(
                    placed.position, placed.dimensions, color,
                    opacity=0.7, name=product_name, edge_color=edge_color
                ))
            
            if placed.product.fragile:
                for line in self.create_fragile_grid(placed.position, placed.dimensions):
                    fig.add_trace(line)
        
        # Layout
        fig.update_layout(
            title="Roll Container Packing - Final Configuration",
            scene=dict(
                xaxis=dict(title='Length (cm)', range=[0, self.config.container.length * 1.1]),
                yaxis=dict(title='Width (cm)', range=[0, self.config.container.width * 1.1]),
                zaxis=dict(title='Height (cm)', range=[0, self.config.container.height * 1.05]),
                aspectmode='manual',
                aspectratio=dict(
                    x=self.config.container.length / self.config.container.height,
                    y=self.config.container.width / self.config.container.height,
                    z=1.0
                ),
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.2),
                    center=dict(x=0, y=0, z=0),
                    up=dict(x=0, y=0, z=1)
                )
            ),
            showlegend=False,
            height=1000,
            margin=dict(l=80, r=80, t=80, b=80)
        )
        
        fig.show()
