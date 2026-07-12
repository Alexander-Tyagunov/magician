# orm — MyBatis

MyBatis is a **SQL mapper**, not a full ORM. You write the SQL; MyBatis maps
params in and rows out, killing JDBC boilerplate. No dirty-checking, no
persistence context, no automatic schema. Reach for it when you want hand-tuned
SQL, legacy/complex queries, stored procs, or fine control over exactly what
hits the DB. Reach for JPA/Hibernate instead when you want entity lifecycle and
generated CRUD.

- Latest: **MyBatis 3.5.19** (Jan 2025). Artifact `org.mybatis:mybatis`.
- Java baseline: **Java 8+** for 3.5.x (bytecode targets 1.8; `java.time` type
  handlers use JDBC 4.0 `getObject(col, Class)`). Tested through JDK 17–25.
- Spring: `mybatis-spring` + `mybatis-spring-boot-starter` for `@Mapper` scan.

## Security — #{} vs ${} (non-negotiable)

This is the single most important MyBatis rule.

- **`#{param}` → PreparedStatement `?`.** MyBatis binds the value safely via
  JDBC. Safe from SQL injection. "Safer, faster and almost always preferred."
- **`${param}` → raw string substitution.** MyBatis "won't modify or escape the
  string" — it is concatenated straight into the SQL text. This is SQL
  injection if the value comes from a user.

DO
- Use `#{}` for every value: WHERE operands, INSERT/UPDATE columns, LIMIT args.
  ```xml
  <select id="find" resultType="User">
    SELECT * FROM users WHERE email = #{email}
  </select>
  ```
- Use `${}` ONLY for SQL identifiers that can't be bound (table/column name,
  `ORDER BY` column, sort direction) — and ONLY after whitelisting the value
  against a fixed allow-list in Java. Never pass user text through raw.
  ```xml
  ORDER BY ${sortColumn} <!-- sortColumn validated against an enum/allow-list -->
  ```

DON'T
- Never put user input in `${}`. `WHERE name = '${name}'` is injectable.
- Don't reach for `${}` to "fix" a binding that failed — that usually means the
  value belongs in `#{}` and you had a mapping/type issue.
- Don't build SQL by Java string concatenation of user input in providers
  either — use `#{}` placeholders inside the built string.

## XML mappers vs annotations

DO
- Prefer **XML mappers** for anything nontrivial: dynamic SQL, joins, reuse.
  XML is "necessary for the most complex mappings."
- Use **annotations** (`@Select`/`@Insert`/`@Update`/`@Delete`, `@Results`,
  `@Result`, `@ResultMap`, `@Options`, `@Param`) for simple, static statements
  where XML overhead isn't worth it.
- Use `@Param("x")` when a mapper method takes multiple params; reference as
  `#{x}`.

DON'T
- Don't expect annotations to do the heavy lifting: they're "limited in
  expressiveness." `@One`/`@Many` **cannot express recursive/circular join
  mappings** (Java annotation limitation). `@Options` can't specify null.
- For dynamic SQL in annotations you must fall back to `@SelectProvider` etc.
  (a class+method returning the SQL) — clunkier than XML `<if>`/`<foreach>`.
- Don't mix `resultType` and `resultMap` on one statement — one or the other.

## Dynamic SQL (XML)

Four elements cover it: `if`, `choose/when/otherwise`, `trim/where/set`,
`foreach`. Tests are OGNL expressions.

DO
- `<where>` strips a leading `AND`/`OR` and omits `WHERE` when empty. Use it
  instead of hand-managing `1=1`.
  ```xml
  <select id="search" resultType="User">
    SELECT * FROM users
    <where>
      <if test="name != null"> AND name = #{name}</if>
      <if test="minAge != null"> AND age >= #{minAge}</if>
    </where>
  </select>
  ```
- `<set>` for updates — prepends `SET`, trims trailing commas.
- `<foreach>` for `IN` lists — bind each element with `#{item}` (still
  parameterized, still safe):
  ```xml
  DELETE FROM users WHERE id IN
  <foreach item="id" collection="ids" open="(" separator="," close=")">
    #{id}
  </foreach>
  ```
  Attributes: `collection`, `item`, `index`, `open`, `close`, `separator`,
  `nullable`. For a Map, `index`=key, `item`=value.
- `<bind>` to build a LIKE pattern safely, then bind with `#{}`:
  ```xml
  <bind name="p" value="'%' + name + '%'"/>
  ... WHERE name LIKE #{p}
  ```
- `<choose>/<when>/<otherwise>` when exactly one branch should apply.

DON'T
- Don't build LIKE with `LIKE '%${name}%'` — injectable. Use `<bind>` +`#{}`.
- Don't rely on `<foreach>` for huge `IN` lists — most DBs cap parameters
  (e.g. Oracle 1000); batch or use a temp table.

## resultMap

`resultMap` is the most powerful mapping element. Auto-mapping handles matching
column↔property names; declare a `resultMap` for renames, nested objects, and
type control.

DO
- Declare `<id>` for the identity column — MyBatis uses it for instance
  comparison, caching, and nested-result de-duplication.
- `<result column= property=>` for simple fields (name/type mismatches).
- `<association>` = has-one, `<collection ofType=>` = has-many.
- Prefer **nested results (JOIN)** over **nested select** for associations/
  collections to avoid the **N+1 selects problem**.

DON'T
- Don't lazy-nest per row when a single join works — N+1 kills throughput.
- Don't map a collection type in `resultType`; use the contained element type
  and a `<collection>`.

## Session / transaction hygiene

DO
- Always close `SqlSession` — try-with-resources.
- Use mapper interfaces (`session.getMapper(Foo.class)`) for type-safe calls;
  method name matches the statement id.
- Use `ExecutorType.BATCH` for bulk writes; call `flushStatements()`.
- Under Spring, let `@Transactional` + `SqlSessionTemplate` manage sessions —
  don't open your own.

DON'T
- Don't share one `SqlSession` across threads (not thread-safe).
- Default `openSession()` does NOT auto-commit — you must `commit()` writes.

## Sources

- MyBatis 3 home: https://mybatis.org/mybatis-3/
- Mapper XML (#{} vs ${}, resultMap): https://mybatis.org/mybatis-3/sqlmap-xml.html
- Dynamic SQL: https://mybatis.org/mybatis-3/dynamic-sql.html
- Java API / annotations: https://mybatis.org/mybatis-3/java-api.html
- GitHub (version, test matrix): https://github.com/mybatis/mybatis-3
- FAQ (#{} vs ${} injection): https://github.com/mybatis/mybatis-3/wiki/FAQ
- mybatis-spring-boot-starter: https://mybatis.org/spring-boot-starter/
