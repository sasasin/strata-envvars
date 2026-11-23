# `--chunk`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--chunk` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換し、1 未満は 1 に補正 |

## 役割

ベンチマークの prompt prefill と `--serve` の継続的なバッチ処理で、一度の処理にまとめる prompt token 数の目安を設定します。既定値は 512 です。直接生成モードの prefill はこの値で分割されず、`--chunk` はその経路の処理量を変えません。

## 使い方

モデルを使ったベンチマークで prompt chunk を指定する例です。

```sh
strata-inkling --bench --native ./model.strata --chunk 256
```

## 値と既定値

- 値は `--chunk` の次の引数を `std::atoi` で整数変換し、`std::max(1, ...)` で最低 1 にします。0、負数、先頭から整数として読めない文字列（空文字列を含む）は 1 になります。`atoi` が先頭の整数部分だけを読むため、たとえば `256tail` は 256 として扱われます。厳密な数値形式検査や上限値検査はありません（`engine/src/inkling2/ink_main.cpp:413-414`）。
- 値を省略すると共通設定 `BackendOpts::chunk` の初期値 512 が使われます（`engine/src/inkling2/ink_backend.h:17-20`）。
- 同じオプションを複数回指定した場合は、引数走査中に設定値が更新されるため最後の値が残ります（`engine/src/inkling2/ink_main.cpp:379-384,413-414`）。
- 値自体がない場合は `missing value after --chunk` を stderr に出し、終了コード 2 で終了します（`engine/src/inkling2/ink_main.cpp:381-383`）。

## 実行時の動作

- `--bench` では、合成 prompt を `bo.chunk` token 以下の単位に分けて各 slot の `StepBatch` に積み、各単位を `backend->forward_batch` へ渡します。末尾の単位は残り token 数に縮みます（`engine/src/inkling2/ink_main.cpp:166-185`）。
- `--serve` では `chunk_sz` に設定値を取り込み、各処理周回の token budget を `max(chunk_sz, n_active)` にします。まず decode 中の各 slot に1 tokenずつ割り当て、その残りを prefill 中の slot に配分します。そのため設定値は厳密な「リクエストごとの chunk 長」ではなく、同時処理中 slot 数に応じて予算が増えることがあります。起動時の `INFO` 行にも `chunk` 値が出ます（`engine/src/inkling2/ink_serve.h:445,479-481,883-916`）。
- 直接生成モードは prompt 全体の token を1つの `StepBatch` に積んで `forward_batch` を呼ぶため、`--chunk` による分割はありません（`engine/src/inkling2/ink_main.cpp:575-593`）。同じ理由で、`--chunk` を読む設定は `--bench` と `--serve` の処理経路で使われ、`--info`、`--selfcheck`、`--kld-eval`、`--dump-ref` 等では効果が確認できません（`engine/src/inkling2/ink_main.cpp:544-573`）。

## 適用条件と副作用

- `--bench` および `--serve` を含め、トップレベル parser が値を読み込みます。ただし実際に chunk 値を参照するのは上記のベンチマークと serve の経路です（`engine/src/inkling2/ink_main.cpp:413-414,549-573`）。
- `--chunk` は同じ parser に登録されていますが、組み込み `--help` の bench / serve usage には掲載されていません（parser: `engine/src/inkling2/ink_main.cpp:413-414`、help: 同 `:488-498`）。本書は parser と実使用箇所を現行実装の根拠とします。
- この値自体によるファイルやネットワークの副作用は確認できません。serve のネットワーク動作は `--serve` 側の処理です。

## 出力とエラー

- `--serve` の起動時 `INFO` プロトコル行に、補正後の `chunk_sz` が `chunk=<値>` として表示されます（`engine/src/inkling2/ink_serve.h:479-481`）。
- 不足値の場合の stderr と終了コード 2 は「値と既定値」に記載の通りです。先頭に整数部分がない値は parser エラーにならず 1 に補正されます（`engine/src/inkling2/ink_main.cpp:381-383,413-414`）。

## 根拠

- 索引上の tool ID、backend、parser の所在、scope: `docs/cli/README.md:1509-1516`。
- parser、値の変換、引数不足時の処理、help 表示、実行モード分岐: `engine/src/inkling2/ink_main.cpp:379-384,413-414,488-501,544-579`。
- 既定値: `engine/src/inkling2/ink_backend.h:17-20`。
- benchmark の chunked prefill: `engine/src/inkling2/ink_main.cpp:166-185`。
- serve の token budget、decode / prefill 配分: `engine/src/inkling2/ink_serve.h:442-446,479-481,883-916`。
- 直接生成時に prompt を単一 batch に積む経路: `engine/src/inkling2/ink_main.cpp:575-593`。
