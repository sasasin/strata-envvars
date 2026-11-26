# `STRATA_VERIFY_COMPLEMENT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

設定されていると、resident RAM 用の expert 補完領域と、profile から事前充填した GPU expert cache のチェックサムを計算して stderr に出す診断用スイッチです。通常の resident RAM 動作や GPU cache の選択・内容を切り替える値ではありません。ソースコメントも用途を `tests` としています。実装は `FileExpertSource::pin_cache_complement` と `strata generate` の profile fill にあります（`engine/src/core/expert_source.cpp:4699-4716`、`engine/src/program/generate.cpp:9848-9879`）。

## 値と判定

両方の実装で `std::getenv(...) != nullptr` による有無判定だけを行います。文字列の変換・比較はありません。環境変数が未設定なら診断処理を行わず、空文字を含む何らかの値が設定されていれば実行します。したがって `0`、`false`、`0anything`、大文字小文字や前後の空白の違いも無効化しません（`engine/src/core/expert_source.cpp:4699`、`engine/src/program/generate.cpp:9848`）。

| 実行箇所 | unset | 設定時に診断が動く条件 | 設定されていても動かない条件 |
|---|---|---|---|
| 補完領域 | チェックサムを出さない | 補完領域の構築が成功し、`host != nullptr` かつ `bytes > 0` | host 領域がない、または補完サイズが 0 |
| profile fill | cache チェックサムを出さない | `strata generate` が profile fill 経路に入り、環境変数を読む箇所まで到達する | profile が空、または `srcp == nullptr` で fill 経路に入らない |

後者の条件は `if (!profile.empty() && srcp != nullptr)` の内側にあります（`engine/src/program/generate.cpp:9758-9760,9843-9848`）。CLI 引数、設定ファイル、別の環境変数との優先順位や fallback はなく、これらの診断分岐は有無判定だけで独立しています。

## 有効になる条件

- 補完領域側は `--resident-experts` または `--resident-cpu-experts` で `o.resident_cpu_experts` が有効になり、`FileExpertSource::pin_cache_complement` が呼ばれる経路が必要です。呼び出し前に GPU cache は有効かつ全 slot が充填済みでなければならず、GPU 同期にも成功する必要があります（引数設定: `engine/src/program/generate.cpp:4220-4222`、呼び出し: `11908-11910,12077-12080`、前提: `engine/src/core/expert_source.cpp:3985-4003`）。
- 補完領域の診断は、構築・コピーの失敗時にはチェックサム地点へ到達しません。`pin_cache_complement` は失敗を `false` とエラー文字列で返します。呼び出し側は soft mode や RAM budget の設定に応じて fallback の警告を出し、通常は file-backed の読み取り経路へ進みます（`engine/src/core/expert_source.cpp:4686-4690`、`engine/src/program/generate.cpp:12091-12106,12203-12214`）。
- GPU cache 側の診断は profile fill block 内に限られます。profile fill 自体の失敗は `strata generate: the profile fill failed at pair ...` を stderr に出して `1` を返しますが、これはこの環境変数のチェックサム処理より前の別の失敗経路です（`engine/src/program/generate.cpp:9798-9805`）。
- 読み取りはどちらも診断処理の実行地点で都度行われ、関数 `static` などへの cache はありません。起動後にプロセス環境が変更された場合、後の読み取り地点ではその時点の設定有無が使われます。子プロセスへの転送・上書きはこの実装にはありません。

## 実行時の詳細

- 補完領域側では、補完データのコピーと失敗確認が終わった後、host 領域を最大 1 GiB ごとに分割し、最大 8 worker（7 thread と呼び出し thread）で FNV-1a 64-bit hash を計算します。最後に補完 offset 配列と piece hash 列を hash し、`FileExpertSource: cache complement checksum ...` を stderr に出します（`engine/src/core/expert_source.cpp:4686-4716`）。
- profile fill 側では、GPU cache の slot を slot 番号順に並べ、各 slot のデータを `cudaMemcpy(..., cudaMemcpyDeviceToHost)` で読み戻して FNV-1a 64-bit hash を計算します。最大 8 worker で slot を処理し、slot 番号・blob byte 数・hash を順にまとめて `strata generate: expert cache checksum ...` を stderr に出します（`engine/src/program/generate.cpp:9848-9879`）。
- どちらも期待値との比較や、補完元データと GPU cache の一致判定はしていません。補完側は offset と host piece hash を一つの値にまとめ、GPU 側は GPU slot の読み戻し hash をまとめており、相互比較コードはありません（`engine/src/core/expert_source.cpp:4713-4716`、`engine/src/program/generate.cpp:9858-9879`）。GPU 側で読み戻しコピーが失敗した場合は出力に `, A READ-BACK FAILED` が付きますが、そのフラグによる終了・失敗返却はありません（`engine/src/program/generate.cpp:9858-9865,9878-9879`）。

## ログと測定値

設定されていて補完領域が存在する場合、stderr に `FileExpertSource: cache complement checksum %016llx (%.2f GiB, its offsets included)` の形式でチェックサムとサイズを出します（`engine/src/core/expert_source.cpp:4715-4716`）。profile fill 経路では stderr に `strata generate: expert cache checksum %016llx (%zu slots%s)` を出し、読み戻しコピーの失敗時のみ slot 数の後ろに `, A READ-BACK FAILED` が付きます（`engine/src/program/generate.cpp:9878-9879`）。チェックサムの不一致を示すログや、この変数に起因する終了コード変更はありません。資料中にこの診断スイッチの測定値は見つかりませんでした。

## 根拠

- `engine/src/core/expert_source.cpp:3985-4003` — 補完領域構築の前提と GPU cache 同期。
- `engine/src/core/expert_source.cpp:4686-4716` — コピー失敗後の設定有無判定、補完 checksum 計算・出力。
- `engine/src/program/generate.cpp:9758-9760,9798-9805` — profile fill の適用範囲と通常の fill 失敗経路。
- `engine/src/program/generate.cpp:9843-9879` — GPU cache の設定有無判定、readback、checksum と失敗表示。
- `engine/src/program/generate.cpp:4220-4222,11908-11910,12077-12106,12203-12214` — resident CPU experts 引数、補完構築呼び出しと失敗時の扱い。
