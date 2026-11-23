# `--lookup-max-t`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、`root/`） |
| オプション | `--lookup-max-t` |
| 別名 | なし |
| 値 | 整数 `N`。prompt-lookup の窓サイズ上限（トークン数）。 |

## 役割

prompt lookup（文脈内の過去の反復に続いたトークンを候補にする suffix drafter）が、MTP の通常窓より長い検証窓を使えるようにする上限です。serve 中は窓サイズごとの CUDA graph を準備し、適応ポリシーが候補と実測コストに応じて使う窓を選びます。`--lookup-max-t` は MTP 自体の窓を長くする指定ではありません。

## 使い方

```sh
# モデルと serve モードを指定し、prompt-lookup 窓の上限を指定する
strata --native model.gguf --serve --lookup-max-t 12

# 長い prompt-lookup 窓の拡張を無効にする
strata --native model.gguf --serve --lookup-max-t 0
```

## 値と既定値

- parser は次の引数を `atoi` で整数化し、`max(0, 値)` を保存します。負数は `0` になり、数値として読めない文字列も `atoi` の結果 `0` になります。値を省略すると `stderr` に `--lookup-max-t needs a value` を出して終了コード `2` で終了します。複数回指定した場合は走査中に後の値が前の値を置き換えます。 (`engine/src/program/generate.cpp:3837-3842, 4116-4119`)
- `0` はこのオプションによる長い窓への拡張を無効にします。suffix draft 自体の有効・無効は別設定 `--suffix-draft` で決まり、`--lookup-max-t 0` がそれを無効にするわけではありません。正の値を指定した場合、help は `N <= 16` と案内します。parser 自体には `16` を超える値を直接拒否する処理はありませんが、実行時の `--spec` 上限と利用可能な窓サイズにより、窓はビルドの `kVerifyLongT` 以下（通常 16）に制限されます。 (`engine/src/program/generate.cpp:1341-1346, 4116-4119, 5051-5070`; `engine/include/strata/kernels/verify_kernels.hpp:23-31`)
- 省略時は、`STRATA_LOOKUP_MAX_T` が `0` で始まる場合を除き、8 行窓の build、非 Metal、serve、単一 GPU、layer split なし、`--batch` が 1、DFlash2 でない、lookup chain なし、suffix draft 有効、`--spec >= 2` の条件が全て成立すると `12` です。それ以外は `0` です。 (`engine/src/program/generate.cpp:5035-5049`; `engine/include/strata/core/lookup_default.hpp:9-28`)
- 環境変数による既定値判定はオプション未指定時だけ行われます。明示的に `--lookup-max-t 12` を指定すれば、`STRATA_LOOKUP_MAX_T=0` でもその値が優先されます。 (`engine/src/program/generate.cpp:4118, 5038-5049`)

## 実行時の動作

- `N > 0` かつ suffix draft が有効で `--spec >= 2` の場合、MTP 上限が未指定なら現在の `--spec` を MTP 上限に設定し、検証窓の `--spec` を `N` と `kVerifyLongT` の小さい方まで拡張します。以後、`--spec` はこの上限を超えると `strata generate: --spec ...` を `stderr` に出して終了コード `1` になります。suffix draft が無効などこの条件に当たらない場合は、この拡張処理は行われません。 (`engine/src/program/generate.cpp:5051-5070`)
- `--lookup-max-t` が有効なとき、lookup 窓に使えるサイズは MTP のサイズに加え、既定では MTP 上限より大きい候補（MTP+1、MTP+2、`--spec` 以下のサイズ）です。`--lookup-sizes` を指定すると、その追加候補は指定リストのうち `2..--spec` に入る値に絞られます。サイズ指定は `lookup_size_mask` でポリシーに渡されます。 (`engine/src/program/generate.cpp:1505-1526, 16323`; `engine/src/program/generate.cpp:1172-1173`)
- serve 起動時に有効な窓サイズを `stderr` に表示します。各候補サイズの graph は事前に準備され、VRAM 不足ならそのサイズを候補から外し、次に小さい適合サイズを試します。VRAM 不足以外の準備失敗はエラー経路になります。窓サイズごとの graph が追加で VRAM を使うため、上限や候補数を増やすと必要 VRAM も増えます。 (`engine/src/program/generate.cpp:16406-16423`; help の目安: `engine/src/program/generate.cpp:1344-1346`)
- 長い窓は単一会話の prompt/decode に適用されます。batch 窓・pipelined 窓は通常窓上限のままです。layer split では長い窓がサポートされず、複数 stage 時に `stderr` へ上限を知らせた後、`spec` を narrow 窓上限へ戻します。CUDA/HIP の通常窓上限は build により 8 または 16、Metal/SYCL 等は別の build 条件を持ちます。 (`engine/include/strata/kernels/verify_kernels.hpp:23-31`; `engine/src/program/generate.cpp:13178-13183`)
- この機能は候補の検証窓を切り替えるもので、draft policy のコメントでは出力自体は変えないとされています。ただし、ソースだけでは全モデル・全 backend での出力同一性を独立に保証できる範囲までは確認していません。 (`engine/include/strata/spec/draft_policy.hpp:13-19`)

## 適用条件と副作用

- 自動で `12` になる条件は上記のとおり限定的です。Metal は既定値判定で明示的に除外され、複数 GPU、layer split、batch、DFlash2、lookup chain、suffix draft 無効、`--spec < 2` なども既定値 `0` になります。明示値と自動既定値は区別してください。 (`engine/include/strata/core/lookup_default.hpp:23-28`)
- 既定の追加候補サイズは MTP より大きいものだけですが、各候補の graph は個別に準備されます。VRAM 不足の候補は実行中に以後の選択対象から外れます。 (`engine/src/program/generate.cpp:1508-1525, 16409-16423`)
- lookup 上限が narrow 窓を超える場合、serve は penalty history 用バッファを `kVerifyLongT` 分に確保し、GPU にも同サイズを確保します。長い lookup 窓を有効にすることでホスト・GPU メモリ使用量が増える条件があります。 (`engine/src/program/generate.cpp:13134-13145`)

## 出力とエラー

- 引数値の欠落は parser が `stderr` にエラーを出し、終了コード `2` で終了します。 (`engine/src/program/generate.cpp:3837-3842`)
- `--spec` が実行可能上限を超えた場合は `stderr` に許容範囲を表示し、終了コード `1` で終了します。 (`engine/src/program/generate.cpp:5063-5070`)
- lookup graph の準備時に VRAM 不足なら `stderr` にそのサイズを候補から外した旨を表示して縮小したサイズを試します。別種の graph 準備失敗は decode 側で `ERR ...` を出して終了コード `1`、prompt 側ではエラー文字列を返す経路を確認しました。 (`engine/src/program/generate.cpp:16412-16423, 20328-20330, 22631-22635, 22643-22647, 22655-22659`)

## 根拠

- `engine/src/program/generate.cpp:1166-1173` — option の保存値と関連する MTP/lookup sizes の設定。
- `engine/src/program/generate.cpp:1341-1346, 3837-3842, 4116-4119` — help 表示、値の取得、parser 変換。
- `engine/src/program/generate.cpp:5035-5070`、`engine/include/strata/core/lookup_default.hpp:9-28` — 未指定時の環境変数・build・実行条件による既定値、`spec` 拡張と上限検査。
- `engine/src/program/generate.cpp:1505-1526, 16323, 16406-16423`、`engine/include/strata/spec/draft_policy.hpp:13-19` — 候補サイズ、適応ポリシー、graph 準備と VRAM 不足時の縮小。
- `engine/include/strata/kernels/window_limits.hpp:20-25`、`engine/include/strata/kernels/verify_kernels.hpp:23-31` — build ごとの窓上限と長い単一会話窓の制約。
- `engine/src/program/generate.cpp:13134-13145, 13178-13183, 20325-20340, 22631-22680`、`engine/src/core/verify.cpp:3505-3520` — バッファ確保、layer split の扱い、prompt/decode の実使用と長窓の commit 制約。

調査範囲は上記 commit の Strata 所有ソースです。既存バイナリの `--help` 実行、build、GPU 実行、性能測定、テストは行っていません。help の `<= 16` 表示と parser の直接検証範囲を照合し、値そのものに対する上限検査は確認できず、実効上限は `--spec` と build 窓サイズの制約として記載しました。
