# `--native-qsa-indexer`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、`strata generate` の parser） |
| オプション | `--native-qsa-indexer` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

QSA indexer のキー cache 追加処理を、CUDA の native indexer 実装へ切り替える実験用フラグです。native 実装は F16 に丸めた raw key cache、F32 pooling、weighted RMSNorm、text IMRoPE を使います。QSA の正規化・出力 gate を切り替える `--native-qsa` とは独立です（`src/program/generate.cpp:448-449`、`src/kernels/native_qsa_indexer.hpp:8-18`）。

## 使い方

```sh
strata --pack <pack-dir> --tokens 1,2,3 --native-qsa-indexer
```

`--native` preset を使う場合は indexer を含む複数の native 経路がまとめて有効になります（下記参照）。

## 値と既定値

- 値は不要です。parser は引数を bool に設定し、既定値は `false` です。引数を必要とする検査や値の validation はありません（`src/program/generate.cpp:448`、`src/program/generate.cpp:2494`）。
- オプション名だけを渡す形式です。次の引数はこのフラグの値として消費されず、他の引数として解釈されます。
- `--native` を指定すると、このフラグも有効になります（`src/program/generate.cpp:3263-3267`）。

## 実行時の動作

起動処理でフラグ値を CUDA indexer の process-wide 設定へ渡します（`src/program/generate.cpp:3940`）。decode の QSA key append は、enabled の場合 `native_qsa_indexer_append`、無効の場合 `indexer_key_append` を呼び分けます（`src/core/layer.cpp:1227-1233`）。native append は既存 buffer 群に raw key を追加し、F16 相当の丸め、4 cell 単位の pooling、位置に応じた RoPE 処理を行います。形状は index dim 128、block 4、回転次元 64 に固定されています（`src/kernels/native_qsa_indexer.hpp:10-18`、`src/kernels/cuda/native_qsa_indexer.cu:35-38,60-80`）。

Prefill の経路はこのフラグによる分岐がなく、native batch append を利用します。`STRATA_INDEXER_PER_TOKEN` 環境変数が存在すると、batch 呼び出しに代えて token ごとの native append を使います（`src/prefill/prefill.cpp:3371-3386`）。したがって、この CLI フラグは prefill の native/non-native 選択スイッチではなく、主に通常 decode 側の切替設定です。

`--native` preset は `--stream-token`、native BF16、GDN、QSA、RoPE なども有効化し、indexer も有効にします。個別指定の native フラグは A/B 用に残されています（`src/program/generate.cpp:3263-3267`、help 表示 `src/program/generate.cpp:850-855`）。Verify の互換性判定では native indexer が無効なら verify window を不適合として扱います（`src/core/layer.cpp:537-546`）。

## 適用条件と副作用

- native CUDA kernel は固定 geometry のみ受け付けます。append 時に stream の有無、shape、最大 cell 数、4 cell 境界の position base、epsilon、RoPE scaling を検証し、buffer span の alignment・重なりも検査します。条件違反は例外になります（`src/kernels/cuda/native_qsa_indexer.cu:269-298`）。
- 実行中は CUDA kernel を起動して既存の indexer buffer を更新します。別の入力ファイルを開く、ファイルを書き出すといった CLI 副作用はありません。
- native indexer は QSA layer の処理で呼ばれるため、QSA を含まないモデルでの効果・適用可否はこのソース範囲からは確認できません。ソースに示された固定形状以外の backend/build での利用可否も実行確認していません。

## 出力とエラー

このフラグ自体に専用の成功メッセージや独自の parser validation はありません。値不足を要求する処理もありません。未知の引数は parser の一般エラー経路へ進みます。native append の不正引数や kernel launch error は例外として呼び出し元へ伝わり、decode 側では layer error 文字列、prefill 側では `prefill indexer: ...` のエラー文字列として報告されます（`src/program/generate.cpp:2494`、`src/core/layer.cpp:1228-1232`、`src/prefill/prefill.cpp:3386`、`src/kernels/cuda/native_qsa_indexer.cu:273-298`）。具体的な最終 stderr 表記・終了コードは caller による処理を含むため、これらの箇所だけでは一律に断定できません。

## 根拠

- scope と索引リンク: `docs/cli/README.md:1132-1145,1220`。
- parser、default、help、native preset: `src/program/generate.cpp:448-449,850-851,2494,3263-3267,3940`。
- native と既存 decode append の分岐、verify 条件: `src/core/layer.cpp:537-546,1227-1233`。
- native 実装の固定形状・buffer contract: `src/kernels/native_qsa_indexer.hpp:8-18`、`src/kernels/cuda/native_qsa_indexer.cu:35-38,267-298`。
- prefill batch/token append と環境変数条件: `src/prefill/prefill.cpp:3371-3386`。

調査は上記 commit の checkout に含まれるソースを対象としました。CLI help はソース内の usage 文字列を確認し、別の実行バイナリは起動していません。実行時の GPU/backend 差や Release 配布物での挙動は調査していません。
