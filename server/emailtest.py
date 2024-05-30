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
                "Data": "Your subject \"{0}\" has finished processing. Visit https://biomechnet.org/data/{1} to view and download. You can view in-browser visualizations of the uploaded trial data by clicking on each trial name.\n\nThank you for using BiomechNet!\n-BiomechNet team\n\nHaving problems or questions? Do not reply to this email. Please visit the AddBiomechanics forum on SimTK: https://simtk.org/plugins/phpBB/indexPhpbb.php?group_id=2402&pluginname=phpBB".format("SprinterC3D", "SprinterC3D"),
            }
        },
        "Subject": {
            "Charset": CHARSET,
            "Data": "BiomechNet: \"{0}\" Finished Processing".format("SprinterC3D"),
        },
    },
    Source="noreply@biomechnet.org",
)
