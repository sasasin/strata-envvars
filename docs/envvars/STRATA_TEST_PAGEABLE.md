# `STRATA_TEST_PAGEABLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

開発・診断用の切替で、CUDA/HIP と SYCL の prefill が pageable host memory へ fallback する一部の pinned host buffer を、pinned allocation を試さずに pageable 側へ回します。通常時に pinned allocation が失敗した場合の fallback 経路を、pin 可能な環境でも通す用途です。名前と実装コメントが示すとおり、通常利用者向けのモデル設定ではなく、ASan / `MALLOC_CHECK_=3` などで fallback 経路を試す開発・診断用フックです。CUDA/HIP の `PinnedRing` でも pinned slot の使用を抑止し、caller の memory から転送して stream を待つ経路になります。`engine/src/prefill/prefill.cpp:359-363,1156-1168,1454-1479,2576-2602`、`engine/sycl/src/prefill/prefill.cpp:201-208,502-535,1508-1565`、`engine/include/strata/core/pinned_ring.hpp:36-43,48-53,95-113,120-149,172-175`。

## 値と判定

各 reader は `getenv` の結果が null でないことに加えて `e[0] == '1'` を判定します。文字列全体の parse や数値変換はせず、空文字は無効、先頭文字が `1` なら残りの文字列に関係なく有効です。先頭文字の比較は大文字小文字を区別し、空白を読み飛ばしません。各 reader の関数内 `static const bool` に最初の評価結果が保存されます。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP `Prefill::init` と `PinnedRing` | 無効（通常の pinned allocation / slot 利用を試行） | `1`, `10`, `1anything` | 空文字、`0`, `true`, `True`, ` 1`, `01` |
| SYCL `Prefill::init` | 無効（通常の pinned host allocation を試行） | `1`, `10`, `1anything` | 空文字、`0`, `true`, `True`, ` 1`, `01` |

根拠: `engine/src/prefill/prefill.cpp:361-364`、`engine/sycl/src/prefill/prefill.cpp:206-209`、`engine/include/strata/core/pinned_ring.hpp:172-175`。

## 有効になる条件

- Strata の CUDA/HIP または SYCL engine で、該当する prefill buffer 初期化・転送経路が使われる必要があります。Metal の `Prefill::init` は早期に Metal 実装へ委譲し、これらの CUDA/HIP・SYCL fallback 分岐は通りません（`engine/src/prefill/prefill.cpp:2443-2454`）。
- CUDA/HIP の `PinnedRing` による pageable host upload/download にも適用されます。SYCL にはこの `PinnedRing` 実装は使われず、SYCL prefill 内の各 fallback 分岐が対象です（`engine/include/strata/core/pinned_ring.hpp:27-43,95-113`）。
- 値が有効でも、各 buffer の初期化または転送が実行されなければ効果はありません。特に SYCL の mapped routing table は `STRATA_GROUP_COPY=0` のときだけ mapped allocation を検討するため、既定の copy 経路ではこの変数による差はありません（`engine/sycl/src/prefill/prefill.cpp:1508-1546`）。CUDA/HIP の mapped routing table は `STRATA_GROUP_COPY` が先頭 `1` でない場合に allocation を試み、変数が有効なら mapped pinned allocation を飛ばして通常の copy 経路へ進みます（`engine/src/prefill/prefill.cpp:2576-2593`）。
- 他の CLI 引数や環境変数による値の上書きはありません。`STRATA_GROUP_COPY` は routing table の経路選択に別途関わりますが、`STRATA_TEST_PAGEABLE` の値自体を変更しません。
- このフックは、Strata 内の全 pinned allocation を無条件に失敗させるものではありません。たとえば CUDA/HIP の layer split hand-off buffer は別の `cudaHostAlloc` を直接呼び、SYCL staging の `done_seq` / `src_seq` もこの判定より前に `sycl::malloc_host` します（`engine/src/prefill/prefill.cpp:2488-2491`、`engine/sycl/src/prefill/prefill.cpp:508-513`）。

## 実行時の詳細

CUDA/HIP と SYCL の prefill では、`Prefill::init` が stager ring buffer を初期化する際、通常は pinned host allocation を試します。変数が有効ならその試行を飛ばし、`std::vector` の pageable buffer を使います。CUDA/HIP ではさらに、`PinnedUpload::init` が pin buffer の割当てをスキップして upload 時に caller の memory から転送し、routing table の mapped buffer を作らず通常の copy に回し、PLE embedding host buffer を pageable vector にします。SYCL でも mapped routing allocation と PLE embedding の pinned host allocation を同様に抑止します（`engine/src/prefill/prefill.cpp:1156-1168,1454-1479,2576-2602`、`engine/sycl/src/prefill/prefill.cpp:502-535,1508-1565`）。

CUDA/HIP の `PinnedRing::acquire` は `nullptr` を返し、`h2d` は `direct` に移ります。`direct` は caller の memory から `cudaMemcpyAsync` を行って stream を同期します。`d2h_sync` も slot なしで転送後に同期します。`reserve` は有効時に成功を返しますが、slot を確保しません（`engine/include/strata/core/pinned_ring.hpp:36-43,48-53,95-113,120-149`）。

各判定は関数内 static に保存され、プロセス中に環境を変更してもその判定をすでに評価した reader には反映されません。CUDA/HIP prefill、SYCL prefill、CUDA/HIP `PinnedRing` はそれぞれの reader で評価されます。CLI の優先順位や子プロセスへの転送処理はこの実装にはありません。

## ログと測定値

この変数を有効にしたことを知らせる専用ログはありません。該当分岐は pinned allocation を飛ばすか pageable fallback を選ぶだけです。通常の転送失敗時には `PinnedRing` が `strata: pinned upload of %zu bytes failed: %s\n`、`strata: upload of %zu bytes failed: %s\n`、または `strata: download of %zu bytes failed: %s\n` を stderr に出します。画像 embedding upload が失敗した場合は prefill のエラー `prefill: the image embedding upload failed` に伝播し、`generate` 呼び出し元が `strata generate: %s\n` として stderr に出して終了コード 1 を返します。環境変数の有効化そのものは失敗や終了を起こしません（`engine/include/strata/core/pinned_ring.hpp:82-113`、`engine/src/prefill/prefill.cpp:4511-4517,24118-24123`、`engine/sycl/src/program/generate.cpp:13354-13358`）。この変数について条件付き測定値を記載した Strata 資料は確認できません。

## 根拠

- 値判定と cache: `engine/src/prefill/prefill.cpp:361-364`、`engine/sycl/src/prefill/prefill.cpp:206-209`、`engine/include/strata/core/pinned_ring.hpp:172-175`
- CUDA/HIP prefill の staging、upload、routing table、PLE fallback: `engine/src/prefill/prefill.cpp:1156-1168,1454-1479,2576-2602`
- SYCL prefill の staging、routing table、PLE fallback: `engine/sycl/src/prefill/prefill.cpp:502-535,1508-1565`
- CUDA/HIP pinned ring の fallback と同期: `engine/include/strata/core/pinned_ring.hpp:36-43,48-53,79-113,120-149`
- CUDA/HIP Metal 早期分岐、prefill 起動と初期化失敗の伝播: `engine/src/prefill/prefill.cpp:2443-2454`、`engine/src/program/generate.cpp:24115-24123`
- SYCL prefill 起動と初期化失敗の伝播: `engine/sycl/src/program/generate.cpp:13352-13358`
