# `STRATA_PRIMARY_DEVICE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`strata generate` がエンジン自身の主 GPU として使う、可視デバイス ordinal を選びます。既定の 0 から別の ordinal に変えると、主セッションの GPU、そこに置くモデル等の資源、および helper expert cache / peer tier が主 GPU とみなすデバイスが変わります。これは Windows HIP の固定列挙順で主 GPU を選び直せるようにする機能として説明されていますが、環境変数の読み取りと主デバイス設定自体には Windows 専用の guard がありません。NVIDIA/HIP のどちらでも engine の GPU ordinal として扱われます（`engine/src/program/generate.cpp:4764-4773`, `5449-5466`; 主デバイスの保存先 `engine/src/core/device.cu:87-92`）。

値は `--serve` の有無にかかわらず engine 起動時に扱われます。これを変更する CLI 引数はなく、`--layer-split` が指定された起動では、値が 0 以外なら layer split の準備後に組み合わせを拒否します（`engine/src/program/generate.cpp:4857-4864`）。

## 値と判定

主デバイス番号の本読み取りは `generate.cpp` 内の lambda で一度行い、`std::atoi` の結果が正ならその値、そうでなければ 0 にします。文字列全体の妥当性検査はありません。したがって未設定、空文字、`0`、`-1`、`true`、`0anything` はいずれも 0 です。`2`、`+2`、` 2`、`2junk` は `atoi` が読む数値接頭部が正なので 2 になります。大文字小文字や末尾文字は判定せず、空白は `atoi` の変換規則に従います（`engine/src/program/generate.cpp:4768-4773`）。

| 条件 | 未設定・空文字 | 有効になる値（例） | 無効値・範囲外の扱い |
| --- | --- | --- | --- |
| `strata generate` の主デバイス選択 | 0 | 可視 ordinal の正の整数。例: `1`、`2` | `atoi` が 0 以下を返せば 0。正の値が可視 GPU 数以上なら最終選択時にエラー終了。数値接頭部の後ろは検査しない |
| HIP queue priming の補助参照（HIP、`STRATA_HIP_GFX906` 以外） | 0 | `atoi` の結果が正ならその ordinal | `atoi` が 0 以下なら 0。可視 GPU 数以上なら queue priming を黙って中断（主選択時のエラーとは別経路） |
| CUDA の適応既定値用 VRAM 読み取り | 0 | 0 より大きく、可視 GPU 数未満の値 | 値が範囲外または 0 以下ならデバイス 0 の VRAM を読む |
| Linux NUMA カード選択（Metal 以外） | 0 | `atoi` の結果が正ならその ordinal | 正の ordinal が可視範囲外ならカード情報は unknown 扱いになり得る。これ自体は主選択の範囲検査ではない |

これらの変換箇所は同じ文字列を個別に `getenv` / `atoi` しています。`atoi` の変換不能文字列は 0 になり、数値の接頭部があればその値を返します。`atoi` の戻り値に対する明示的な overflow 検査はありません（`engine/src/program/generate.cpp:3490-3493`, `4442-4446`, `4632-4639`, `4768-4773`）。

## 有効になる条件

- `strata generate` の GPU engine 経路で有効です。主デバイス値の設定箇所に `--serve` 条件はなく、通常の CLI 実行と server 実行の両方で選択処理へ進みます（`engine/src/program/generate.cpp:4764-4773`, `5449-5466`）。
- 正の値は GPU runtime が列挙する可視 ordinal でなければなりません。`HIP_VISIBLE_DEVICES` / `CUDA_VISIBLE_DEVICES` などで可視 GPU が変われば、この ordinal の対象も変わります。正の範囲外値は主デバイス設定時に拒否されます（`engine/src/program/generate.cpp:5453-5464`）。
- 0 は既定の主 GPU です。値を設定していても `atoi` の結果が 0 以下なら 0 のままです。
- `--layer-split` との併用は、正の主 device ordinal では未対応です。起動は `strata generate: STRATA_PRIMARY_DEVICE %d is not supported with a layer split yet` を stderr に出し、終了コード 2 になります（`engine/src/program/generate.cpp:4857-4864`）。
- 主デバイスは AMD HIP build では実行対象 GPU のアーキテクチャ検査にも含まれます。build がコードを持たない GPU なら同検査がエラーを報告して終了コード 1 になります（`engine/src/program/generate.cpp:4974-4986`）。
- CLI 引数による上書きはありません。`--split-device` は layer split の後段 GPU を指定する別設定で、主デバイスを置き換えず、正の `STRATA_PRIMARY_DEVICE` との組み合わせは拒否されます（`engine/src/program/generate.cpp:4066` は引数解析、`4857-4864` は拒否分岐）。
- `STRATA_PRIMARY_DEVICE` が正の場合、remote expert helper は主 ordinal を除いた可視 GPU を順番に割り当て候補とします。peer tier も主 ordinal と helper ordinal の間を使い、helper が主 ordinal と同じなら拒否します（`engine/src/program/generate.cpp:4882-4894`; `engine/src/core/remote_experts.cpp:71-81`; `engine/src/core/peer_experts.cpp:192-216`）。
- `STRATA_HIP_QUEUE_PRIME` が `0` でない、または未設定で gfx12 Linux 自動判定が有効な HIP build では、queue priming 関数も `STRATA_PRIMARY_DEVICE` を参照します。`STRATA_HIP_QUEUE_PRIME` が `0` ならその関数は先に戻り、対象変数の補助参照もありません。Windows HIP では自動 priming は行わず、明示的な queue-prime 値がある場合に限って先へ進みます（`engine/src/program/generate.cpp:3474-3517`）。
- CUDA の compute capability が全可視 GPU で同じ場合、`STRATA_PRIMARY_DEVICE` が指す GPU の VRAM を適応既定値へ渡します。ただし読み取り値が正の可視 ordinal でない場合は ordinal 0 を使います（`engine/src/program/generate.cpp:4421-4449`）。
- Linux の非-Metal 経路で複数 NUMA node のカード情報を作る場合、主カードの ordinal として参照します。layer split、peer device、または remote cache がある場合は複数カードを調べるため主 ordinal だけに限定しません（`engine/src/program/generate.cpp:4615-4653`）。

## 実行時の詳細

`generate.cpp` は主 ordinal の確定前に、HIP queue priming、CUDA 適応既定値の VRAM 選択、Linux NUMA カード選択のために環境変数をそれぞれ再読込します。これらの箇所は本選択と同じ `atoi` 正値規則を使いますが、無効・範囲外値の扱いは表のとおり異なります。主選択値はその後 lambda 内で一度読み、`strata::core::set_primary_device` に保存され、プロセス内の `primary_device()` が参照します。環境変数の値を関数内 static cache にする実装ではありません（`engine/src/program/generate.cpp:3490-3493`, `4442-4446`, `4632-4639`, `4768-4773`; `engine/src/core/device.cu:87-92`）。

主 GPU を実際に切り替えるのは `primary_device != 0` のときです。runtime の可視数を照会し、範囲外なら stderr に `strata generate: STRATA_PRIMARY_DEVICE=%d: no such visible device (%d visible)` を出して終了コード 2、`cudaSetDevice` が失敗すれば `strata generate: STRATA_PRIMARY_DEVICE=%d: cudaSetDevice failed: %s` を出して終了コード 1 です。成功時は `strata generate: primary device from STRATA_PRIMARY_DEVICE: CUDA%d` を stderr に出します（`engine/src/program/generate.cpp:5453-5466`）。この切り替え後の主スレッドで、後続のモデル・GPU 資源処理が進みます。同じファイルは後のセッション作成でも `OnDevice(primary_device)` を使います（`engine/src/program/generate.cpp:7712-7714`）。

主 ordinal は `device.cu` のプロセス内グローバル値として保持されます。helper ordinal は主デバイス以外から組み立てられ、remote helper と peer tier は `primary_device()` を使って主 GPU と区別します（`engine/src/core/device.cu:87-92`; `engine/src/program/generate.cpp:4884-4894`; `engine/src/core/remote_experts.cpp:71-81`; `engine/src/core/peer_experts.cpp:192-216`）。本変数に関する子プロセスへの転送やリクエスト単位の再読込は確認できません。

## ログと測定値

- 0 の場合、主デバイス選択成功ログは出ません。
- 正の有効値なら成功時に `strata generate: primary device from STRATA_PRIMARY_DEVICE: CUDA%d` を stderr に出します。
- 正の範囲外値は主選択時に可視数付きのエラーを出し、終了コード 2 です。ただし `--layer-split` 併用時は先に併用不可のエラーを出して終了コード 2 になります。
- `cudaSetDevice` 失敗は runtime のエラー文字列を含めて stderr に出し、終了コード 1 です。
- 性能測定値はこの変数の値と条件に結び付けた Strata 資料を確認できなかったため記載しません。

これらの文字列・終了経路は `engine/src/program/generate.cpp:4857-4864`, `5453-5466` にあります。

## 根拠

- `engine/src/program/generate.cpp:3474-3517` — HIP queue priming の条件と主 ordinal の補助読込。
- `engine/src/program/generate.cpp:4421-4449` — CUDA architecture default 適用前の主 GPU VRAM 選択。
- `engine/src/program/generate.cpp:4615-4653` — Linux NUMA 対象カードの選択。
- `engine/src/program/generate.cpp:4764-4773` — 主 ordinal の parse とプロセス内 state への保存。
- `engine/src/program/generate.cpp:4857-4864`, `4882-4894` — layer split との拒否、helper device の決定。
- `engine/src/program/generate.cpp:4974-4986`, `5449-5466`, `7712-7714` — HIP architecture 検査、主 GPU の選択・ログ・終了経路、後続 session の device scope。
- `engine/src/core/device.cu:87-92`, `engine/include/strata/core/device.hpp:51-57` — primary device の保存と参照 API。
- `engine/src/core/remote_experts.cpp:71-81`, `engine/src/core/peer_experts.cpp:192-216` — helper / peer が主 ordinal を除外して検査する処理。
