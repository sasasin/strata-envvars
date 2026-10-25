# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-plan` |
| コマンド | `strata-plan`（サブコマンドなし） |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

引数走査中に使い方と `--state` の既定動作に関する補足を標準出力へ表示し、終了コード `0` で終了します。計画の計算・表示には進みません。`strata-plan` は CMake が `src/plan/plan_main.cpp` から生成する単体 CLI です（`CMakeLists.txt:323-331`）。

## 使い方

```sh
strata-plan --help
```

短縮形も同じ分岐で受け付けます。

```sh
strata-plan -h
```

## 値と既定値

値は不要です。`--help` と `-h` は同じ parser 分岐に入ります。ヘルプ分岐は引数を左から走査して最初に到達した時点で即時終了します。したがって、ヘルプより前に値を要求するオプションが末尾にあり値がない場合は、ヘルプを表示する前に stderr へ `<option> needs a value` を出し、終了コード `2` になります（`src/plan/plan_main.cpp:18-25,44-50`）。

## 実行時の動作

標準出力に次の構文を表示します。

```text
usage: strata-plan [--max-context N] [--vram BYTES] [--dense B] [--embd B]
                   [--workspace B] [--state B] [--pool B]
```

続けて、`--state` を省略した場合は `0` ではなく geometry に基づく GDN recurrence と conv history の容量が使われること、その容量を以前 `0` としていた場合の差について、ソース内の説明文を表示します。ヘルプ分岐は戻り値 `0` で `main` を終えるため、通常の計画計算や `DoesNotClose` 判定は行いません（`src/plan/plan_main.cpp:44-50,56-71`）。

引数走査の前に、先行するオプションが値を書き換えることはありますが、ヘルプ経路ではその値を使った計算やファイル・ネットワーク・プロセス操作はありません。ヘルプ自体に値の検証処理はありません。

## 適用条件と副作用

このフラグは引数走査で認識されたときに適用されます。引数なし、または通常のオプションの後に指定できます。先行する未知の引数がある場合は、その時点で `unknown argument: ...` を stderr に出し終了コード `2` となり、後続の `--help` には到達しません（`src/plan/plan_main.cpp:18-25,44-54`）。

`--help` は出力以外の副作用を持ちません。位置引数や不明なフラグを許容する包括的なヘルプ parser ではなく、実装が列挙したオプション構文を表示します。

## 出力とエラー

- 成功時: usage と補足文を stdout に表示し、終了コード `0`。
- ヘルプより前に値のない値付きオプションがある場合: stderr に `<option> needs a value`、終了コード `2`。
- ヘルプより前に未知の引数がある場合: stderr に `unknown argument: <argument>`、終了コード `2`。

これらのエラー経路は引数走査の順序から生じます（`src/plan/plan_main.cpp:18-25,44-54`）。

## 索引との差異と調査範囲

索引 [`docs/cli/README.md`](../../README.md) は `strata-plan/root/--help.md` を掲載していますが、alias は記載していません。parser では `-h` も `--help` と同じ分岐として受理されます（`src/plan/plan_main.cpp:44`）。索引は今回の依頼範囲外のため変更していません。

調査は指定 revision のソースに基づきます。既存バイナリや Release 配布物の `--help` は実行・照合していません。

## 根拠

- `src/plan/plan_main.cpp:13-25` — 引数走査と値付き引数が末尾にある場合のエラー処理。
- `src/plan/plan_main.cpp:44-54` — `--help` / `-h` の認識、表示内容、終了コード、未知引数の処理。
- `src/plan/plan_main.cpp:56-71` — ヘルプ後に続く通常計算・失敗経路との境界。
- `CMakeLists.txt:323-331` — `strata-plan` 実行ファイルの定義。
- `docs/cli/README.md:1404-1415` — `strata-plan` の索引項目と文書配置。
