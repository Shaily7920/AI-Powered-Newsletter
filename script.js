document.getElementById("subscription-form").addEventListener("submit", function (event) {
    event.preventDefault(); // Prevent default form submission

    let formData = new FormData(this);

    fetch("/set_preferences", {
        method: "POST",
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.redirect) {
            window.location.href = data.redirect;  // Redirect to personalized newsletter
        } else {
            alert("Subscription successful!");
        }
    })
    .catch(error => console.error("Error:", error));
});
