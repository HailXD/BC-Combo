from flask import Flask, render_template, jsonify, request
import pandas as pd
from itertools import combinations

app = Flask(__name__)

# Global variables to store data
cats_data = None
combos_data = None
cat_hierarchy = {}

def load_data():
    """Load and process the TSV files"""
    global cats_data, combos_data, cat_hierarchy
    
    # Load cats data
    cats_data = pd.read_csv('cats.tsv', sep='\t')
    
    # Load combos data
    combos_data = pd.read_csv('combos.tsv', sep='\t')
    
    # Build cat hierarchy (evolution chain)
    for _, row in cats_data.iterrows():
        forms = []
        if pd.notna(row['First']):
            forms.append(row['First'])
        if pd.notna(row['Evolved']):
            forms.append(row['Evolved'])
        if pd.notna(row['True']):
            forms.append(row['True'])
        if pd.notna(row['Ultra']):
            forms.append(row['Ultra'])
        
        # Each cat can be satisfied by any of its evolved forms
        for i, form in enumerate(forms):
            if form not in cat_hierarchy:
                cat_hierarchy[form] = set()
            # Add all higher evolution forms
            cat_hierarchy[form].update(forms[i:])

def parse_effect_strength(effect):
    """Parse effect string to extract type and strength"""
    if pd.isna(effect):
        return None, 0
    
    effect = str(effect)
    strength_map = {'(Sm)': 1, '(M)': 2, '(L)': 3, '(XL)': 4}
    
    for strength_text, strength_value in strength_map.items():
        if strength_text in effect:
            effect_type = effect.replace(strength_text, '').strip()
            return effect_type, strength_value
    
    # Handle special cases like "Eva Angel Killer" EffectUP (XL)
    if 'EffectUP' in effect:
        for strength_text, strength_value in strength_map.items():
            if strength_text in effect:
                effect_type = effect.split('EffectUP')[0].strip().replace('"', '')
                return effect_type, strength_value
    
    return effect, 1  # Default strength if not found

def get_combo_units(combo_row):
    """Extract all units from a combo row"""
    units = []
    for i in range(1, 6):  # Unit1 to Unit5
        unit_col = f'Unit{i}'
        if unit_col in combo_row and pd.notna(combo_row[unit_col]):
            units.append(combo_row[unit_col])
    return units

def can_satisfy_combo(combo_units, available_cats):
    """Check if available cats can satisfy a combo"""
    for required_cat in combo_units:
        found = False
        for available_cat in available_cats:
            # Check if available cat is the required cat or an evolution of it
            if available_cat == required_cat:
                found = True
                break
            # Check if available cat is in the hierarchy of required cat
            if required_cat in cat_hierarchy and available_cat in cat_hierarchy[required_cat]:
                found = True
                break
        if not found:
            return False
    return True

def find_combo_combinations(target_effect_type, target_strength, max_cats=5):
    """Find all possible combinations of combos that achieve target effect and strength"""
    matching_combos = []
    
    # Find all combos that match the effect type
    for _, combo in combos_data.iterrows():
        effect_type, strength = parse_effect_strength(combo['Effect'])
        if effect_type == target_effect_type:
            units = get_combo_units(combo)
            matching_combos.append({
                'name': combo['Name'],
                'effect_type': effect_type,
                'strength': strength,
                'units': units,
                'unit_count': len(units)
            })
    
    # Sort by strength descending to prioritize higher strength combos
    matching_combos.sort(key=lambda x: x['strength'], reverse=True)
    
    results = []
    
    # Try different combinations of combos
    for combo_count in range(1, len(matching_combos) + 1):
        for combo_combination in combinations(matching_combos, combo_count):
            # Calculate total strength
            total_strength = sum(combo['strength'] for combo in combo_combination)
            
            if total_strength >= target_strength:
                # Get all unique cats needed
                all_cats = set()
                for combo in combo_combination:
                    all_cats.update(combo['units'])
                
                if len(all_cats) <= max_cats:
                    combo_names = [combo['name'] for combo in combo_combination]
                    results.append({
                        'combos': combo_names,
                        'total_strength': total_strength,
                        'cats': list(all_cats),
                        'cat_count': len(all_cats)
                    })
    
    # Remove duplicates and sort by efficiency (fewer cats and combos first)
    unique_results = []
    seen_cats = set()
    
    for result in results:
        cats_tuple = tuple(sorted(result['cats']))
        if cats_tuple not in seen_cats:
            seen_cats.add(cats_tuple)
            unique_results.append(result)
    
    # Sort by cat count first, then by total strength
    unique_results.sort(key=lambda x: (x['cat_count'], -x['total_strength']))
    
    return unique_results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/effect-types')
def get_effect_types():
    """Get all unique effect types"""
    effect_types = set()
    for _, combo in combos_data.iterrows():
        effect_type, _ = parse_effect_strength(combo['Effect'])
        if effect_type:
            effect_types.add(effect_type)
    
    return jsonify(sorted(list(effect_types)))

@app.route('/api/find-combinations')
def find_combinations():
    """API endpoint to find combo combinations"""
    effect_type = request.args.get('effect_type')
    strength = int(request.args.get('strength', 1))
    max_cats = int(request.args.get('max_cats', 5))
    
    if not effect_type:
        return jsonify({'error': 'Effect type is required'}), 400
    
    try:
        results = find_combo_combinations(effect_type, strength, max_cats)
        return jsonify({
            'results': results,
            'total_found': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    load_data()
    app.run(debug=True, port=5000)