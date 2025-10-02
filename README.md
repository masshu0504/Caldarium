# Caldarium Medical Document Parsing Framework
This repository provides a project framework for students to use to jump start their work.

## Recommended Usage of This Framework

We recommend that students clone this repository and use it as a starting point (inital commit) for their own github repository which will hold all of the project's data/files/scripts going forward (including: pdfs, python and shell scripts, PostGres dumps, json files, etc.).

### Repository File Structure and Recommended Additions

    caldarium_med_parsing
    ├── Dockerfiles/                                       - (Provided Folder)
    │   └── helper.Dockerfile                              - (Provided File) Needed to run the Helper Container
    ├── schemas/                                           - (Provided Folder) To house the .json schemas
    │   └── invoice.json                                   - (Provided File) The .json schema for the invoice pdfs
    ├── minio_buckets/                                     - (Provided Folder) To house the buckets loaded from and into MinIO
    │   └── invoices/                                      - (Provided Folder) This folder represents the MinIO invoices Bucket which can be loaded into and from MinIO
    |       ├── invoice_T1_gen1.pdf                        - (Provided File) This is an invoice pdf
    |       ├── invoice_T1_gen2.pdf                        - (Provided File) Another invoice pdf...
    |       ├── the rest of the invoices...                - (Provided File) ...
    ├── postgres_dump/                                     - (Not Provided Folder) This folder houses the PostGres dump file
    |   └── med_parsing_dump.sql                           - (Not Provided File) This file will contain your PostGres data that can be loaded into/from the PostGres server
    ├── FastAPI/                                           - (Not Provided Folder) This folder would contain the files that you create, including FastAPI files
    |   ├── your first api files                           - (Not Provided File) FastAPI file
    |   ├── the rest of your api files or other files      - (Not Provided File) FastAPI file or other project file
    ├── Another Project Folder/                            - (Not Provided Folder) Another folder maybe to house .json files if parsing happens before postgres integration
    |   └── Some Project Files                             - (Not Provided Files) .json or other files
    ├── README.md                                          - (Provided File) This file is the one you are reading right now. Once you start this project, it should be modified to represent both this starting framework as well as your contributions.
    ├── docker-compose.yml                                 - (Provided File) Defines the Docker container, services, and their properties.
    ├── export_data.sh                                     - (Provided File) Script to export data from MinIO and PostGres server.
    ├── bootstrap.sh                                       - (Provided File) Script to load data into MinIO and PostGres server.
    ├── schema_validation.py                               - (Provided File) Python script to validation parse .json files against the provided schema.
    ├── Meta Prompt                                        - (Provided File) A prompt you can add when asking questions to an AI chatbot of your choice. Highly recommended for a response that's broken down and easy to understand.
    ├── labelstudio_invoice_label_config_template.xml      - (Provided File) A template that you can copy and paste into the labelstudio label config code editor.
    ├── NOTICE.txt                                         - (Provided File) Contains license for students to use.
    └── .gitignore                                         - (Provided File) Tells github which files to ignore.
    
    
    
    

## Docker Container Setup Instructions and How to Use boostrap and export_data scripts

### Prerequisites

You need to have both Docker and Git installed before-hand.

I recommend Docker Desktop as well. You can use it to easily see if the container/images are running. You can also easily use it to delete the container/images if you need a clean wipe.

You will also need Python installed for schema_validation.py

### 1. Clone the Repository

First, you need to download the code onto your computer:

***git clone https://github.com/j-sh-park/caldarium_med_parsing_start/***

***cd caldarium_med_parsing_start***


#### Explanation:

***git clone*** downloads the repository from GitHub.

***cd*** moves you into the project directory so you can run Docker and scripts from the correct location.

### 2. Build and Start the Docker Services

Next, start all required services (Label Studio, MinIO, PostGres, and any helper containers) using Docker Compose:

***docker compose up -d --build***

#### Explanation:

docker compose up starts all services defined in docker-compose.yml.

***-d*** runs the containers in the background (detached mode).

***--build*** ensures that Docker rebuilds images if there are any changes.

### 3. Enter the Helper Container

In order to execute the export_data.sh and bootstrap.sh scripts, you will need to enter the helper container within your command line.

***docker compose run --rm helper bash***

#### Explanation:

This opens an interactive bash session in the helper container.

***--rm*** ensures the container is removed automatically after you exit.


### 4. Export Data (After Making Changes)

After commiting changes to the PostGres DB or uploading pdfs to MinIO, you can export these changes by running the export_data.sh script.

All PostGres data will be dumped into a postgres_dumps folder as a file named med_parsing_dump.sql. **NOTE:** The  postgres_dumps folder may need to be created before exporting PostGres data.

All files uploaded to MinIO will be saved into folders within the minio_buckets folder. For example, a pdf file named file.pdf stored in MinIO in a bucket named test will be saved into the following file path: minio_buckets/test/file.pdf.

On Windows:

***./export_data.sh***


On Mac/Linux:

***bash export_data.sh***

### 5. Restore Data (Bootstrap)

This script loads pdfs and PostGres data into the MinIO and PostGres servers.

MinIO: If you are pulling a version of the github repo that contains additional pdfs in the minio_bucket folder, those additional files will be loaded into the MinIO server when this script is run.

PostGres: If you are pulling a version  of the github repo that contains different PostGres data in the med_parsing_dump.sql file, that data will be committed to the PostGres server.

On Windows:

***./bootstrap.sh***


On Mac/Linux:

***bash bootstrap.sh***

### 6. Access Services

#### You Can Access the Following in Web Browser

Label Studio (Annotation Tool): http://localhost:8080

For Label Studio you'll have to create your own account.

MinIO (Object Storage): http://localhost:9000

MinIO Login -> username: [minio], password: [minio123]

#### Access Postgres with the Following Details

Host name/address: localhost
port: 5432
user: postgres
password: postgres
db: med_parsing

## Schema Validation

Once you are ready to validate your .json file (hopefully containing fields and values parsed from the pdfs) you will need to execute the schema_validation.py script.

The script takes the following arguments:

1. instance: [REQUIRED] the file path to the .json file you want to compare to the schema.
2. schema: [OPTIONAL, ENABLE WITH '--schema' FLAG] the file path to the .json schema that the instance will be compared against. Default file path is: schemas/invoice.json.

## Licensing

This project is provided under the **Apache 2.0** license.  
See [NOTICE.txt](NOTICE.txt) for details.


# Deliverable Setup Update
- .env.example set up with DB URLS parameters and postgres inputs
- If postgres not set up, install psql shell
- Run psql shell and run: CREATE DATABASE med_parsing;
- After running the database, create the parsed_documents table using this sql:
CREATE TABLE IF NOT EXISTS parsed_documents (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payload JSONB NOT NULL
); - Database now has a table which is ready for inserts
- To insert into the table, run this sql:
INSERT INTO parsed_documents (payload)
VALUES ('{"title": "Test Document", "content": "This is a dummy row."}');

- Insert corresponding fields mentioned earlier in README into .env.example file
- run uvicorn main:app --reload to run the routes
- after running go to [localhost:8000](http://127.0.0.1:8000)/docs to test the routes


- To log into the database, run docker exec -it caldarium-ls-postgres-1 psql -U postgres -d med_parsing
- Then create the table for insertion using this command: CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS parsed_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    extracted_data JSONB NOT NULL
);

- In the docker-compose.yml file, also add this service: fastapi:
    build:
      context: .
      dockerfile: Dockerfiles/fastapi.Dockerfile
    ports:
      - "8000:8000"
    depends_on:
      ls-postgres:
        condition: service_healthy
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: med_parsing
      POSTGRES_HOST: ls-postgres
      POSTGRES_PORT: 5432
    networks:
      - backend


