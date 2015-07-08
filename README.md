

 * environment & directory based parameters
 * multi level templates




1. basic cl

```
samtools view -Sb input.sam > output.bam
```


2. annotate cl to identify components -> perfect provenance tracking

```
{x} samtools view -Sb {<} input.sam > {>} output.bam
```


3. expand wildcards

```
{x} samtools view -Sb {<} {name~*}.sam > {>} {name}.bam
```


4. reuseable snippets

```
{x} samtools view -Sb {<} {{name~*}}.sam > {>} {{name}}.bam
```
