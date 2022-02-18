import boto3

ses_client = boto3.client("ses", region_name="us-west-2")
CHARSET = "UTF-8"

response = ses_client.send_email(
    Destination={
        "ToAddresses": [
            "keenonwerling@gmail.com",
        ],
    },
    Message={
        "Body": {
            "Text": {
                "Charset": CHARSET,
                "Data": "Your subject \"{0}\" has finished processing. Visit https://biomechnet.org/my_data/{1} to view and download. You can view in-browser visualizations of the uploaded trial data by clicking on each trial name.\n\nThank you for using BiomechNet!\n-BiomechNet team\n\nP.S: Do not reply to this email. To give feedback on BiomechNet, please contact the main author, Keenon Werling, directly at keenon@stanford.edu.".format("SprinterC3D", "SprinterC3D"),
            }
        },
        "Subject": {
            "Charset": CHARSET,
            "Data": "BiomechNet: \"{0}\" Finished Processing".format("SprinterC3D"),
        },
    },
    Source="noreply@biomechnet.org",
)
