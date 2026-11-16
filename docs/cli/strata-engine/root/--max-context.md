# `--max-context`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン、root 引数） |
| オプション | `--max-context` |
| 別名 | なし |
| 値 | 整数 `N`（token/cell 数） |

## 役割

エンジンが確保し、prompt と生成に利用できる context/KV/state の最大 cell 数を指定する。大きくすると長い prompt や生成を収容できる一方、session 状態の確保量に影響する。モデルの学習済み context 長を変更する指定ではなく、RoPE の拡張設定は別途扱われる。

## 使い方

```sh
strata --pack /path/to/pack --tokens '1,2,3' --max-context 8192 --max-new 256
```

この例では通常 engine の token ID 入力に対して context 上限を 8192 cell、生成上限を 256 token として起動する。実際の起動にはモデル/pack など実行環境に合った入力が必要。

## 値と既定値

- 値は必須。parser は `--max-context` の直後の引数を `std::atoll` で `int64_t` に変換する。引数が欠けると stderr に `--max-context needs a value` を出して終了コード 2 で終了する。
- 既定値は `4096`。短い数値で始まる不正な文字列を厳密に拒否する処理は parser にない。`atoll` の変換結果が 0 となる値や、負数は後続の正数検査で拒否される。
- 有効条件は `max_context > 0`、`max_context <= 2147483639`（`2^31 - 1 - 8`）、かつ `max_new <= max_context` と prompt token 数が `max_context - max_new` 以下であること。`--max-new` の既定値は 16。
- `--serve` では各リクエストについて `prompt token 数 + max_new + 8 <= max_context` を検査する。このため、起動時の prompt なし検査を通っても、実際のリクエストは context 不足で拒否されることがある。

## 実行時の動作

- parser が設定した値は session の GPU buffer サイズ計算と初期化に渡される。QSA state の `max_cells` や KV page 数、画像位置テーブルの大きさにも反映されるため、必要なデバイス/ホストメモリはモデル、KV 設定などと合わせて変わる。
- 生成時は context の位置上限として使われ、上限に達すると生成は継続できない。serve では起動時に `READY <max_context>` を stdout に出し、リクエストごとに上限を検査する。
- `--rope-scaling`、`--rope-scale`、RoPE 関連の値とは独立した指定。通常 engine は解決済み RoPE 設定と学習済み context を比較して stderr に表示するが、`--max-context` 単独で RoPE scaling を有効化しない。
- `--max-new` と合わせて prompt と生成を収容する必要がある。context 値は session config にも保存対象設定として記録される。

## 適用条件と副作用

- この文書は `src/program/generate.cpp` の通常 engine parser を対象とする。`strata` は `--native` / `--model` が指す GGUF の family を先に判定し、Qwen3.5 MoE では別実装へ委譲する。別 parser のオプション仕様はこの root scope に含めない。
- session state を CUDA device memory に確保し、失敗すれば推論を開始できない。`--max-context` が大きい場合の必要メモリ量や実行性能の具体値は、モデル、KV 形式、backend、GPU などに依存し、ここでは一律に確定できない。
- vision が有効な場合、画像位置テーブルは `max_context + 64` cell 分をホスト側に用意し、device に転送する。

## 出力とエラー

- 不正な範囲、`--max-new` との不整合、起動時 prompt が収まらない場合は stderr に `strata generate:` のエラーを出し、終了コード 2 で終了する。
- serve のリクエストが `prompt + max_new + 8` の条件を満たさない場合は stdout に `ERR prompt ... exceeds the context ...` を出して、そのリクエストを拒否し次の処理へ進む。
- session buffer の確保失敗は stderr に `session state allocation failed` を出し、終了コード 1。session 初期化失敗も終了コード 1。
- 生成中に position が context 上限に達した場合は stderr に `ran out of context at position ...` を出して終了コード 2。

## 根拠

- `src/program/generate.cpp:736-741` — `Options::max_context` の型と既定値。
- `src/program/generate.cpp:1225-1227` — help にある値の説明と既定値。
- `src/program/generate.cpp:3667-3672, 3695-3697` — 引数欠落時の処理と `atoll` による parser 登録。
- `src/program/generate.cpp:3645-3657` — Qwen3.5 MoE を family 判定後に別 parser へ委譲する経路。
- `src/program/generate.cpp:4870-4877, 5781-5785` — context の上限、正数、`--max-new`・prompt との起動時 validation とエラー終了。
- `src/program/generate.cpp:5757-5765` — vision 位置テーブルの `max_context + 64` サイズと device allocation。
- `src/program/generate.cpp:6094-6107, 6757-6781, 7300-7312` — session/KV 容量見積もり、QSA state の最大 cell 数、session buffer の確保・初期化。
- `src/program/generate.cpp:13085-13096` — `max_context` を session config に含める処理。
- `src/program/generate.cpp:15201-15202, 17291-17296` — serve の READY 出力と prompt/request 上限エラー。
- `src/program/generate.cpp:21780-21785` — 生成位置が context 上限に達した場合の失敗経路。
- `docs/cli/README.md:1000-1074` — `strata-engine` root 引数の索引と、この文書の予定リンク。
