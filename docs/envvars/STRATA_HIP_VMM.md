# `STRATA_HIP_VMM`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

HIP ビルドで、弾力的な K/V (`--kv-grow`) が使う仮想メモリ機能の利用可否を切り替えます。環境変数が無効化値に一致する場合、Strata はHIP仮想メモリAPIやデバイスの対応状況を調べず、`vmm_available()` を false のままにします。その結果 `--kv-grow` の条件が満たされず、この機能は無効になります。

この変数はCUDA実装では読まれません。CUDA側の `vmm_available()` は別のAPI解決・デバイス属性判定を行い、この変数による無効化分岐はありません。

## 値と判定

HIP実装は `std::getenv("STRATA_HIP_VMM")` の結果が存在し、かつ先頭文字が `'0'` の場合だけ初期化を中止します。文字列全体や数値としての妥当性は検査しません。

| 値 | HIPでの判定 |
|---|---|
| 未設定 | 無効化しない。通常のVMM対応確認へ進む |
| 空文字 | 無効化しない。通常のVMM対応確認へ進む |
| `0` または `0` で始まる文字列（例: `0abc`） | VMM判定を中止し、利用不可とする |
| その他の非空文字列（例: `1`, `true`, `false`, `-1`） | 無効化しない。通常のVMM対応確認へ進む |

したがって `false` は無効化値ではなく、`0anything` は無効化値です。大文字小文字、前後の空白、後続文字は解釈されません。

## 有効になる条件

- `STRATA_USE_HIP` が定義され、`STRATA_HIP_GFX906` が未定義で、`HIP_VERSION_MAJOR >= 6` のビルドでのみ、この環境変数を読むHIP実装がコンパイルされます。
- その実装でも、変数が `0` 始まりでなく、かつ選択中デバイスが仮想メモリ管理を報告し、割り当て粒度を取得できた場合に限り `vmm_available()` が true になります。確認に失敗した場合は false です。
- `--kv-grow` 自体は、単一GPU、プロファイル指定、全K/VがVRAM内、全expertがRAM側、expert cache有効、remote expertなし、`--batch` なし、`--vram-elastic` なし、`--peer-device` なし、さらに `vmm_available()` が true の場合に有効化されます。要求値は `STRATA_KV_GROW` が非空なら先頭文字が `0` 以外で要求、`0` なら無効です。未設定または空文字ならCLIの `--kv-grow` / `--no-kv-grow` に従います。この要求値が有効でも上記条件を満たさなければ無効です。
- CUDA、Metal、gfx906、およびHIP 6未満ではHIP側の環境変数分岐は使われません。非対応ビルドの実装は `vmm_available()` を常に false にします。

## 実行時の詳細

HIP側の判定は `api()` の `std::call_once` 内で一度だけ行われ、その結果はプロセス内で保持されます。環境変数を初期化後に変更しても再判定されません。無効化された場合、この `api()` の初期化ではデバイス照会やVMM粒度照会を行いません。

`--kv-grow` または `STRATA_KV_GROW` が要求されているのにVMM非対応などの理由で有効化できない場合、生成コードは stderr に `strata generate: --kv-grow is off (one GPU, a profile, the whole K/V in VRAM, every expert in RAM, no --batch, --vram-elastic or --peer-device)` を出します。この文言は個々の失敗理由を特定せず、必要条件をまとめて示します。`STRATA_HIP_VMM=0` だけを設定して `--kv-grow` を要求していない場合、この無効化ログは出ません。

## 根拠

- `src/core/vmm.cpp:154-168,188-210`: HIP実装のコンパイル条件、変数の先頭文字判定、対応属性と粒度の確認、初期化の一回性。
- `src/core/vmm.cpp:215-216,299-314`: VMM利用可否の公開と、HIP以外の該当しないビルドでの常時false実装。
- `src/program/generate.cpp:5147-5164`: `--kv-grow` の要求値、適用条件、無効時ログ、設定反映。
- `docs/DETAILS.md:366-372`: `--kv-grow` の設計説明と、HIP (ROCm 6+) における `STRATA_HIP_VMM=0` の概要。測定結果は同資料の `373` 行以降に記載されていますが、この文書では性能値を独自に再検証していません。
