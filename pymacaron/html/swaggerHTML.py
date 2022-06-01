SWAGGER = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Swagger UI</title>
  <link href="https://fonts.googleapis.com/css?family=Open+Sans:400,700|Source+Code+Pro:300,600|Titillium+Web:400,600,700" rel="stylesheet">
  <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/3.24.2/swagger-ui.css" >
  <style>
    html
    {
      box-sizing: border-box;
      overflow: -moz-scrollbars-vertical;
      overflow-y: scroll;
    }
    *,
    *:before,
    *:after
    {
      box-sizing: inherit;
    }
    body {
      margin:0;
      background: #fafafa;
    }
  </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/3.24.2/swagger-ui-bundle.js"> </script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/3.24.2/swagger-ui-standalone-preset.js"> </script>
<script>
window.onload = function() {
  var spec = JSON.parse(atob("%s"));
  // Build a system
  const ui = SwaggerUIBundle({
    spec: spec,
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [
      SwaggerUIBundle.presets.apis,
      SwaggerUIStandalonePreset
    ],
    plugins: [
      SwaggerUIBundle.plugins.DownloadUrl
    ],
    layout: "StandaloneLayout"
  })
  window.ui = ui
}
</script>
</body>
</html>
"""

BASETEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Swagger UI</title>
  <link href="https://unpkg.com/tailwindcss@^1.0/dist/tailwind.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Roboto+Mono">
  <style>
    body {
        font-family: 'Roboto Mono', sans-serif;
    }
  </style>
</head>
<body>
    <div class="flex flex-col">
        <h1 class="text-3xl mx-auto mt-10 mb-2 hover:text-red-500 hover:underline"><a href="http://pymacaron.com/" target="_blank">Pymacaron</a></h1>
        <h2 class="text-xl mx-auto">Microservices made easy</h2>
        <div class="text-md mx-auto mt-6">
            <h2 class="text-xl mx-auto mb-2">Endpoints:</h2>
            <ul id="references"></ul>
        </div>
    </div>
<script>
    const pages = %s
    const capitalize = (string) => {
        return string.charAt(0).toUpperCase() + string.slice(1).toLowerCase();
    }
    pages.forEach(page => {page.file = page.file.split(".")[0]})
    window.addEventListener('DOMContentLoaded', () => {
        const frame = document.getElementById("references")
        pages.forEach(page => {
            const element = document.createElement("li", page)
            element.innerHTML = `
            <a href="/docs/${page.file}">
                <div class="px-4 py-2 bg-red-500 rounded-md mb-2 text-center text-white font-medium">
                    <span class="font-bold">${capitalize(page.file)}:</span><span class="mx-2">${page.title}</span><span class="italic">v${page.version}</span>
                </div>
            </a>
            `
            frame.appendChild(element)
        })
    })
</script>
</body>
</html>
"""
