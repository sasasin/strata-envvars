# `DS4_CHUNK_SGEMM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`hc_mix_chunk()` 内の Metal ビルド用分岐は、未設定なら融合 `hc_mix()` を使い、設定されていれば F32 `cublasSgemm` と `hc_mix_scale()` を使う意図のコードです（`src/dsv41/ds4_model.cu:3557-3572`）。ただし、現 HEAD の呼び出し経路ではこの環境変数判定は実行されません。Metal では呼び出し元が `hc_mix_chunk()` を通らず `hc_mix_split()` を直接呼び、Metal 以外では helper 内の判定が `#if defined(STRATA_METAL)` によってコンパイル対象から外れるためです（`src/dsv41/ds4_model.cu:8108-8115,8341-8348`）。

## 値と判定

helper 内の判定に到達した場合、値の内容ではなく `std::getenv()` が null かどうかだけを見ます。

| 状態 | helper 内の分岐（Metal ビルド時） |
|---|---|
| 未設定 | `hc_mix()` を呼び、成功扱いで戻る |
| 設定あり（空文字を含む） | `cublasSgemm` の F32 GEMM と `hc_mix_scale()` へ進む |

文字列の変換、数値判定、境界値や無効値の処理はありません。CLI 引数や別の環境変数による上書きも、このコードにはありません。ただしこの分岐へ到達する呼び出し元は現 HEAD では確認できず、上表は helper 本体に書かれた条件の説明であって、現行実行経路で利用者が切り替えられる挙動ではありません。

## 有効になる条件

分岐自体は `STRATA_METAL` が定義されたビルドにだけ含まれますが、そのビルドでは `layer_chunk()` の attention と MoE の両方が `hc_mix_split()` を直接呼び、`hc_mix_chunk()` は呼びません（`src/dsv41/ds4_model.cu:8108-8115,8341-8348`）。このため、Metal では環境変数を設定してもこの helper 内の判定は到達不能です。

Metal 以外では両箇所から `hc_mix_chunk()` が呼ばれますが、helper 内の `#if defined(STRATA_METAL)` 節がビルド時に除外されます。その場合は `DS4_CHUNK_SGEMM` の値にかかわらず `cublasSgemm` と `hc_mix_scale()` の経路です（`src/dsv41/ds4_model.cu:3559-3572,8112-8115,8345-8348`）。

したがって、調査対象 commit のソースには名前の直接参照があるものの、現行 call site から実行可能な環境変数制御としては確認できません。サーバーモード、モデル状態、CLI、キャッシュによる追加条件も見つかりません。

## 実行時の詳細

`hc_mix_chunk()` の helper 本体にある参照は呼び出しのたびに `std::getenv("DS4_CHUNK_SGEMM")` を評価し、static cache は使いません（`src/dsv41/ds4_model.cu:3557-3564`）。ただし前述のビルド条件と全呼び出し元の分岐により、現 HEAD の通常の到達経路ではその読み取り自体が起きません。

Metal 以外で実行される helper の SGEMM が失敗すると、`err` に `cublasSgemm (mHC mixes)` を設定して `false` を返します（`src/dsv41/ds4_model.cu:3565-3570`）。呼び出し元の `layer_chunk()` は失敗を上位へ返します（`src/dsv41/ds4_model.cu:8113-8114,8346-8347`）。この SGEMM エラー経路も環境変数による切り替えではありません。変数専用のログや警告はありません。

## 根拠

- 環境変数を読む helper と SGEMM / scale 分岐: `src/dsv41/ds4_model.cu:3557-3572`
- attention の Metal 分岐と非 Metal の helper 呼び出し: `src/dsv41/ds4_model.cu:8108-8115`
- MoE の Metal 分岐と非 Metal の helper 呼び出し: `src/dsv41/ds4_model.cu:8341-8348`
- 候補名の唯一の参照: `src/dsv41/ds4_model.cu:3560`
