# Self-hosted ML Flow deployment

This directory contains Terraform that describes an ML Flow deployment. It is an app container running on ECS, sitting behind an Oauth2 proxy.

This approach was taken from [this blog post](https://getindata.com/blog/deploying-secure-mlfow-aws/). The only major departure is switching out Globus auth for Google auth.

## How to change the delpoyed resources

1. Create your own tfvars file from the example.prod.tfvars. (At time of writing there is no sensitive content in it, so you should be able to use it as is.)

2. Make your terraform edits.

3. Run terraform!

```
terraform apply -var-file="prod.tfvars"
```