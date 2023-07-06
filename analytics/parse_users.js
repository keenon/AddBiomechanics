const fs = require('fs');

try {
  const rawText = fs.readFileSync('./users.json', 'utf8');
  const data = JSON.parse(rawText);
  let emails = [];
  let text = "";
  for (const user of data.Users) {
    for (const attr of user.Attributes) {
      if (attr.Name === 'email') {
         emails.push(attr.Value);
         text += attr.Value + '\n';
      }
    }
  }
  console.log(emails.length);
  console.log(emails);
  let domains = [];
  for (const email of emails) {
    const domain = email.split('@')[1];
    if (!domains.includes(domain)) {
        domains.push(domain);
    }
  }
    console.log('Domains: '+domains.length);
  fs.writeFileSync('./emails.txt', text);
} catch (err) {
  console.error(err);
}

