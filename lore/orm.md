# ORM / data layer — core

*Shared across the JVM: Hibernate/JPA, jOOQ, MyBatis behave identically from Java/Kotlin/Scala/Groovy (examples in Java).*

DON'T concatenate user input into SQL/HQL/JPQL — SQL injection. ALWAYS parameterize.
- JPA/Hibernate: `q.setParameter("t", v)` with `:t` (named) or `?1` (positional). Never `"...where x='"+v+"'"`.
- jOOQ: type-safe DSL binds automatically. `DSL.val(v)`=safe bind; `DSL.inline(v)`=literal (unsafe w/ untrusted input). Plain SQL (`create.fetch(sql, args)`) is the escape hatch — pass values as `?` bind args, never string-build.
- MyBatis: `#{v}`=PreparedStatement bind — use for ALL values. `${v}`=raw substitution → injection; only for trusted metadata (table/column names), never user input. IN clause: `<foreach>` + `#{item}`.

DO: named params + `@NamedQuery` (validated at startup). Watch N+1 (fetch joins / `@BatchSize`). Wrap writes in a transaction.

Version cue (match namespace to Hibernate major — don't mix):
- 7.x: `jakarta.persistence.*`, JPA 3.2, Java 17.
- 6.x: `jakarta.persistence.*`, Java 11+.
- 5.x: `javax.persistence.*`, Java 8. (Jakarta EE 9 renamed `javax`→`jakarta`.)
- Entity: `@Entity` (non-final, no-arg ctor), `@Id`, `@GeneratedValue`. Config keys: `jakarta.persistence.jdbc.url/user/password` (6/7); `hibernate.dialect` rarely needed. jOOQ 3.21+; MyBatis 3.5.x.

Deep dive when writing non-trivial orm — read lore/orm/{jpa-hibernate,jooq,mybatis,choosing-and-pitfalls}.md

Sources: docs.hibernate.org/orm/current · jooq.org/doc/latest/manual · mybatis.org/mybatis-3
