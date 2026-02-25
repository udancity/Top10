# Assume this is the existing code for stock_analysis.py

def generate_html(data):
    # Current implementation of the generate_html function
    html_content = '<html><body>'
    html_content += '<h1>Stock Analysis</h1>'
    for stock, value in data.items():
        html_content += f'<p>{stock}: {value}</p>'
    html_content += '</body></html>'
    return html_content

def main():
    # Placeholder for main function
data = {'AAPL': 150, 'GOOGL': 2800}
# Call to generate_html needs to be added here

if __name__ == '__main__':
    main()