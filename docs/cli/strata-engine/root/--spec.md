# `strata --spec`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root 引数） |
| オプション | `--spec` |
| 別名 | なし |
| 値 | 整数 `N`。推論検証窓のトークン数。ビルドの検証窓上限以下であること |

## 役割

生成開始後の通常 decode に代えて speculative decoding を有効にし、1 回の検証で扱う窓幅を指定します。窓には直前の確定 token と最大 `N-1` 個の draft token が入り、検証後は一致した draft と次の token を確定します。draft が不要な通常 decode は `--spec 0`（または省略時の非 Metal 既定値）です。MTP draft layer や DFlash2 を使う場合も、この値が窓幅の基準になります。

## 使い方

```sh
# モデル・token 入力など通常の必須引数に加えて、4 token の検証窓を指定
strata --pack MODEL --tokens-file PROMPT.txt --spec 4 --expert-profile PROFILE --expert-cache 4
```

`--expert-profile`、`--expert-cache`、token graph に対応する residency table がない状態で speculative loop に入ると起動処理がエラーになります。パスや cache 値は使用環境に合わせてください。

## 値と既定値

- parser は次の引数を `std::atoi` で整数化して `Options::spec` に代入します。省略時は Metal build で `2`、それ以外の build で `0` です（`engine/src/program/generate.cpp:1010-1017,4040`）。
- parser 自体に値の下限・形式の厳密な検査はありません。したがって非数値文字列は `atoi` の変換結果 `0` として扱われます。重複指定は同じ変数への逐次代入なので最後の値が残ります（同 `:4040`）。
- 起動時に prompt lookup などによる自動調整を適用した後、現在の build の検証窓上限を超えていれば `2..上限` の範囲を示す診断を stderr に出して終了コード `1` で終了します（同 `:5091-5098`）。明示値に固定の上限があるのではなく、通常は `kVerifyNarrowT`、suffix lookup 窓が有効な場合は `kVerifyLongT` が上限です。
- `0` は plain decode です。負数についても parser に拒否処理はなく、通常の spec loop 起動条件（`spec > 0`）を満たしません。ただし負数を明示する利用は文書化されておらず、他 option の組合せについて同等性を保証するものではありません（同 `:1010-1017,24455-24466`）。

## 実行時の動作

値は `Options` に格納され、通常生成ループは prompt の最終位置以降で `spec > 0` の場合に speculative loop へ移行します。loop は verifier を `o.spec` 幅で初期化し、draft 候補を含む窓を検証します。spec loop に入ったとき residency table がなければ「`--expert-profile`、`--expert-cache` と token graph が必要」と stderr に出し、終了コード `2` で終了します（`engine/src/program/generate.cpp:24455-24466,24484-24505`）。

窓幅に関係する主な相互作用は次のとおりです。

- `--suffix-draft` が有効（既定値 3）で `--spec >= 2`、かつ `--mtp-max-t` が未指定なら、現在の値を MTP の上限として保存し、`--spec` を最大 8 まで 2 増やします。lookup が通常の MTP draft より長い窓を使えるようにする調整です（同 `:1158-1162,5033-5039`）。
- `--lookup-max-t` と suffix draft が有効なら、`--spec` は lookup の窓幅に応じて `kVerifyLongT` まで引き上げられることがあります。`--lookup-chain` が有効なら chained lookup を含む窓を最大 8 に広げます（同 `:5079-5089`）。
- `--mtp-max-t` が正数なら MTP 自身の最大窓を `min(--mtp-max-t, --spec)` に制限します。これにより長い窓幅を suffix/lookup 側に残せます（同 `:1512-1523,24835-24837`）。
- `--draft dflash2` では窓幅がカードクラス別 cap（または `--draft-cap`）を上回る場合、stderr に cap 診断を出して `--spec` を cap に下げます。DFlash2 起動失敗時に MTP fallback を選び、`--draft-mtp-spec` を指定していた場合は MTP 用の幅へ下げる経路もあります（同 `:8298-8303,8325-8326`）。
- MTP を指定していて `--spec < 2` の場合、MTP は「`--spec T (T >= 2)` なしでは無視」と stderr に出され、MTP 指定がクリアされます。`--spec` 自体は plain decode として残ります（同 `:8243-8248`）。

speculative loop は各 round の検証結果に従って出力 token を確定します。正常終了時は stdout に `speculation` の round 数・窓幅・draft acceptance 集計を出し、条件により窓サイズ等の集計も表示します（同 `:25250-25274`）。

## 適用条件と副作用

- 共通 engine parser の root option です。Qwen3.6 family に振り分けられた後の専用 parser は索引で別 scope (`strata-engine/qwen36`) とされているため、この文書の対象外です（`docs/cli/000_cli_tools.md:7-11`、`docs/cli/README.md:1036-1041,1240-1248`）。
- speculative decoding は通常生成の prompt 読み込み完了後に始まり、prefill 自体を speculative 化するものではありません（`engine/src/program/generate.cpp:24440-24466`）。
- `--spec` の拡張・縮小は起動時の option 調整と drafter 準備時に行われます。GPU 上では verifier/drafter の window buffers や graph 等を用います。実際に割り当てる資源量は build、backend、モデル、ほかの option に依存し、この調査だけでは一定値を示せません。
- 既定値 `2` は Metal build 固有です。`--spec` に明示値を渡すとその既定値より優先されます（同 `:1013-1017`）。

## 出力とエラー

- 検証窓が build 上限を超える場合: `strata generate: --spec N: a speculative window holds 2..K tokens` を stderr に出し、終了コード `1`（`engine/src/program/generate.cpp:5096-5098`）。
- spec loop の residency table がない場合: 必須条件を示す診断を stderr に出し、終了コード `2`（同 `:24484-24488`）。
- MTP 指定が `--spec < 2` の場合: MTP を無視する診断を stderr に出し、MTP を外して続行（同 `:8243-8248`）。
- DFlash2 でカード cap に達した場合: stderr に cap の診断を出し、自動補正後の窓幅で続行（同 `:8298-8303`）。

## 根拠

- `engine/src/program/generate.cpp:1010-1017` — `Options::spec` の意味と Metal / 非 Metal の既定値。
- `engine/src/program/generate.cpp:1349-1352` — engine help にある option 説明（補助情報。既定の setup 値に関する記載は一般 parser の既定値と同義ではない）。
- `engine/src/program/generate.cpp:4040` — `--spec` を `atoi` で読み込む parser 分岐。
- `engine/src/program/generate.cpp:5033-5039,5079-5098` — suffix/lookup/chain による窓幅調整と build 上限検査。
- `engine/src/program/generate.cpp:8243-8248,8298-8303,8325-8326` — MTP の minimum 条件、DFlash2 cap と fallback 時の調整。
- `engine/src/program/generate.cpp:24455-24505,25250-25274` — speculative loop の開始、residency 前提、verifier 起動と終了時出力。
- `docs/cli/000_cli_tools.md:7-11`、`docs/cli/README.md:1036-1041,1204-1207,1240-1248` — tool ID、root scope、索引上のリンクと Qwen3.6 別 scope。
