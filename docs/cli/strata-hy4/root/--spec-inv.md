# `--spec-inv`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル） |
| オプション | `--spec-inv` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換し、0 以外なら有効、0 なら無効 |

## 役割

SpecInfer の検証窓に使う MLA の batch-invariant 分割を切り替えます。有効時は、最大 16 トークンの窓でも単一トークン時と同じ基準で split-K の分割数を選ぶため、各行の集約順を単一トークン decode に合わせます。既定では有効です。

## 使い方

```sh
# DFly2 を使うオフライン生成で batch-invariant 分割を無効化する例
strata-hy4 --model MODEL.strata --tokens prompt.txt --gen 32 --draft dfly2 --spec-inv 0
```

オフライン実行で SpecInfer 経路に入るには、`--draft dfly2` と正の `--gen` が必要です。この例では通常の生成出力も発生し、既定の出力先 `.` に `gen_ids.txt` を書きます。既存ファイルを避ける場合は `--out` に新しい出力先を指定してください。

## 値と既定値

- 引数は必須です。`atoi` の結果が 0 以外なら `SpecCfg::inv` を `true`、0 なら `false` にします。値の範囲検証はありません。数値として解釈できない文字列は `atoi` により 0 となり、無効扱いになります。
- `SpecCfg::inv` の初期値は `true` です。複数回指定した場合、parser が順に処理して最後の値が残ります。
- 値が欠けると parser の `nxt()` が標準出力へ `ERR --spec-inv needs a value` を出し、終了コード 2 で終了します。

## 実行時の動作

オフラインでは `--draft dfly2` かつ `--gen` が正で、`--dfly-alloc-only` が指定されていない場合に SpecInfer が使われます。そのとき生成処理が `Spec` を構築し、`SpecCfg::inv` に応じて `g_mla_batch_invariant` を設定します（`engine/src/hy4flash/run/hy4_main.hip.cpp:701-703, 992-1000`、`engine/src/hy4flash/run/hy4_spec.hip.h:74-76, 93-96`）。通常の `--draft off` や `--gen 0` では `Spec` を作らないため、この設定は反映されません。

サーバーモードでは `--spec-inv` の設定が `ServeOpts::spec` に渡されます。実際に反映されるのは drafter が利用可能で、serve chunk が 8 以上となり `Spec` が構築された場合です。`--draft off`、小さい chunk、または drafter 初期化失敗時には speculative decode が使われず、この値の効果もありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-556`、`engine/src/hy4flash/run/hy4_serve.hip.h:320-341`）。

有効時、`mla_attn.hip.cpp` の split 数計算は `M <= 16` の窓を `M = 1` と同じ基準で扱い、batch invariant の因果 attention では workspace の最大 key 数も単一トークン相当の扱いにします。無効時は窓サイズ `M` に応じた基準へ戻ります（`engine/src/hy4flash/run/mla_attn.hip.cpp:1409-1423, 2048-2059`）。

相互作用として、`--mla-inv` も `g_mla_batch_invariant` を parser 時点で直接設定しますが、SpecInfer が動くと `Spec` 構築時に `--spec-inv`（省略時は既定の有効）がその値を再設定します。したがって speculative 経路では `--spec-inv` 側が有効値になります。SpecInfer を使わない経路では `--spec-inv` は global を変更せず、`--mla-inv` の設定が別途使われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:426, 441`、`engine/src/hy4flash/run/hy4_spec.hip.h:95`）。

## 適用条件と副作用

このオプション自体は設定値をメモリ上の `SpecCfg` に格納し、SpecInfer の開始時に MLA の global 設定を更新します。ファイルやネットワークを直接操作する処理はありません。切り替えで MLA の split 数と workspace 見積もりが変わるため、実行時間・メモリ使用量への定量的な影響は GPU、入力、実行条件に依存し、このソース調査では測定していません。

## 出力とエラー

- オプション値が欠ける場合は前述の `nxt()` のエラー経路で終了コード 2 になります。
- `atoi` による数値変換後の値に対する範囲 validation や専用の警告出力は確認できませんでした。
- 不明な引数は標準エラーへ `unknown arg ...` を出して終了コード 2 です（`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383, 426`: 引数値の取得、必須値の欠落時出力・終了、および `atoi(...) != 0` による設定。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-30, 74-96`: `SpecCfg::inv` の既定値と `Spec` 構築時の global 設定。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701-703, 992-1000`: オフライン実行で SpecInfer を選ぶ条件と `Spec` の利用。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-556`、`engine/src/hy4flash/run/hy4_serve.hip.h:320-341`: サーバーへの設定転送と drafter 状態による `Spec` 作成条件。
- `engine/src/hy4flash/run/mla_attn.hip.h:124-127`、`engine/src/hy4flash/run/mla_attn.hip.cpp:1409-1423, 2048-2059`: global の意味、split 数と workspace 見積もりへの適用。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:426, 441`: `--spec-inv` と `--mla-inv` の parser 定義。
