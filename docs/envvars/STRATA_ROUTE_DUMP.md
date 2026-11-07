# `STRATA_ROUTE_DUMP`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

検証 window の expert dispatch が受け取った routing を、指定ファイルへテキストで追記します。ソースコメント上の用途はベンチ用 replay placement の入力です。生成・推論結果を制御する値ではなく、出力先のパスです。

この読み取りは `src/core/expert_source.cpp` の `expert_pool_dispatch_multi()` にのみあります。対応する SYCL 実装 `sycl/src/core/expert_source.cpp` にはこの変数の読み取りがなく、同名の設定で SYCL 側が出力することは確認できません。ソースにはベンチ用とのコメントがありますが、実装上はベンチモード判定をせず、後述の dispatch 条件を満たす経路で出力します。

## 値と判定

| 環境値 | 動作 |
|---|---|
| 未設定 | 出力しない。`getenv()` が null になり、ファイルを開かない |
| 空文字 | 出力しない。`f[0] == '\0'` でファイルを開かない |
| 空でない文字列 | 文字列全体をファイル名として `fopen(path, "a")` で開く。既存ファイルには追記し、存在しない場合は作成を試みる |
| 無効なパス、権限不足などで open 失敗 | `fopen()` が null を返すため出力しない。専用の警告・エラー処理はない |

数値変換、範囲制限、大文字小文字の判定はありません。相対パスの場合、プロセスの作業ディレクトリを基準に解決されます（`fopen` に渡す前のパス変換はありません）。

## 有効になる条件

- `expert_pool_dispatch_multi()` が呼ばれる検証 window の経路であること。通常の単一 token 用 `expert_pool_dispatch()` にはこの読み取りがありません。
- 関数が失敗済みでなく、window の token 数と routing 幅の初期検査を通過していること。
- 計画テーブルを処理する `d.plan != nullptr && n <= kMaxWindowEntries && n <= d.plan->cap` の分岐に入ること。この条件外では環境変数を読まず、出力もしません。
- `src/core/expert_source.cpp` の実装が使われる backend であること。対応する SYCL 実装には出力コードがありません。

CLI や設定ファイルとの優先順位はありません。値はファイル出力を有効にするかと、そのパスだけを指定します。

## 実行時の詳細

環境変数は計画分岐に最初に入ったとき、関数ローカル `static` 初期化で一度読みます。ファイルもその時点で append モードで一度開き、同じ `FILE*` をプロセス内で使い続けます。初回の判定後に環境変数を変更しても再読込・再オープンしません。初回に未設定・空文字だった場合も無効状態がキャッシュされます。

ファイルを開けた場合、各 layer-window について次の1行を書きます。

```text
layer n_tok nd nmiss | expert_id:rows:res ...
```

expert は routing に初めて現れた順で並びます。`rows` はその expert に routing された window 内の行数、`res` は `1` が GPU cache resident、`0` が nonresident miss、`2` が tail-skip 対象です。先頭の `nmiss` はこの計画処理で数えた miss 数で、tail-skip が有効なら対象を除いた後の数になります。記録は PCIe share の最終割り当てを示すものではなく、ソースコメントにあるようにオフライン placement replay 用の routing/状態記録です。

各行は `fprintf()` と改行文字の `fputc()` で書きます。open 失敗や書き込みエラーを検査して stderr に警告したり、処理を失敗扱いにしたりする経路はありません。明示的な flush もこの箇所にはありません。

## 根拠

- `src/core/expert_source.cpp:4887-4909` — multi-token dispatch の入口、失敗・window 範囲検査。
- `src/core/expert_source.cpp:4936-4940` — GPU plan 処理の分岐条件。
- `src/core/expert_source.cpp:4963-4984` — tail-skip による miss 数の更新。
- `src/core/expert_source.cpp:4986-4999` — 用途コメント、環境値の読み取りと static cache、append open、記録内容。
- `src/program/generate.cpp:1420-1427,11773-11776` — serve の検証 window から multi-token dispatch に渡す経路。
- `sycl/src/core/expert_source.cpp:2547-2586` — 対応する SYCL multi-token 実装に `STRATA_ROUTE_DUMP` の読み取りがないこと。
