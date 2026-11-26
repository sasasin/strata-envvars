# `STRATA_FILE_RELEASE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows で file-backed expert の GPU 転送後に、その expert が占めていた read-only file mapping の完全なページ範囲を working set から外す処理を有効にする。mapping 自体を解除したり、resident complement や staging buffer を解放したりする設定ではない。通常は無効で、`FileExpertSource::release()` が呼ばれたときだけ作用する。実装は CUDA/HIP 系の `engine/src/core/expert_source.cpp` と SYCL 系の `engine/sycl/src/core/expert_source.cpp` にある。両実装とも `_WIN32` のときだけ環境変数を読む。

## 値と判定

Windows 実装は `std::getenv` の結果を文字列全体で `std::strcmp(v, "1") == 0` と比較し、関数内 `static const bool` に保存する。未設定は無効、空文字も無効で、`1` との完全一致だけが有効。数値変換・trim・大文字小文字変換はしないため、`01`、`1anything`、`true`、` 1`、`1 `、`0` は無効。値の境界や負数の解釈はなく、`"1"` 以外はすべて同じ無効扱いとなる。非 Windows では `getenv` 自体がコンパイル対象外で、関数は常に `0` を返す。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Windows (`_WIN32`) | 無効 | 文字列全体が `1` | 空文字、`0`、`true`、`01`、`1anything`、前後空白付きなど `1` 以外 |
| Windows 以外 | 変数を読まない。常に無効 | なし | すべて（実装は常に `0`） |

読み取りは `release()` の最初の呼び出し時に一度だけ行う。プロセス起動後に値を変えても反映されず、同じプロセスでは後から再評価されない。ここに CLI 引数や別の環境変数との優先順位・上書き処理はない。`engine/src/core/expert_source.cpp:3933-3940`、`engine/sycl/src/core/expert_source.cpp:1609-1616`。

## 有効になる条件

- Windows ビルドであること。CUDA/HIP 系と SYCL 系の両実装に Windows 用分岐がある。Linux 等では環境変数を読まず、release は `0` を返す（`engine/src/core/expert_source.cpp:3933-3940,3979-3982`、`engine/sycl/src/core/expert_source.cpp:1609-1616,1655-1658`）。
- `FileExpertSource::release()` が呼ばれること。呼び出し元には、GPU cache への転送完了後の expert、adaptive tier の入替後、prefill が借りた cache slot の refill 完了後がある（例: `engine/src/program/generate.cpp:15216-15221,15873-15881,20520-20529`; SYCL: `engine/sycl/src/program/generate.cpp:8823-8829,9319-9326,11360-11365`）。
- `release()` 内で有効値のほか、file mapping が開いていて (`base_ != nullptr`)、layer/expert index が範囲内であること。CUDA/HIP 系はさらに unmapped 状態でないことを確認する。条件を満たさない呼び出しは何もせず `0` を返す（同上）。
- CLI モード、モデルの GPU 配置、resident complement の有無はこの変数の値判定を変えない。ただし、呼び出し元が release を実行しない経路では効果もない。`FileExpertSource` は generate 側で生成される（`engine/src/program/generate.cpp:8498`、`engine/sycl/src/program/generate.cpp:4645`）。

## 実行時の詳細

有効な呼び出しでは、expert の file span から OS page size にそろった内部ページ範囲を計算し、両端の共有・端数ページを除いた完全なページだけ `VirtualUnlock` に渡す。通常の連続 blob では `mapped_blob()` の範囲を使い、GGUF の role 別配置では3つの role span を個別に処理して戻り値を合算する。戻り値は処理対象として渡した byte 数であり、物理 RAM が実際に回収された量の測定ではない（`engine/src/core/expert_source.cpp:3941-3978`、SYCL: `engine/sycl/src/core/expert_source.cpp:1617-1654`）。

この処理は mapping を閉じず、後続の file read は同じ mapping を使える。値が無効、mapping が不適用、index が不正、または対象となる完全ページがない場合は `0` で何もしない。GPU への copy が完了してから呼ぶ箇所では、転送元 file page の working set を整理する用途である（呼び出し順の例: `engine/src/program/generate.cpp:15208-15221`、`engine/sycl/src/program/generate.cpp:8810-8829`）。

## ログと測定値

通常の成功時にこの関数自身が出すログはない。`VirtualUnlock` が失敗し、Windows error が `ERROR_NOT_LOCKED` 以外の場合は stderr に `FileExpertSource: cannot trim mapped pages for layer %lld expert %lld (%llu bytes, Windows error %lu)\n` を出して flush し、その span の戻り値を `0` にする。`ERROR_NOT_LOCKED` はこの実装では成功相当として扱う（`engine/src/core/expert_source.cpp:3954-3967`、SYCL: `engine/sycl/src/core/expert_source.cpp:1630-1643`）。呼び出し元の多くは戻り値を捨てるため、成功 byte 数のログや終了コードへの反映はない。

`docs/DETAILS.md:290-292` は Windows の working-set hint と説明しており、現行実装と一致する。関連する測定報告 `docs/bench-results/2026-10-04-windows-mapped-release/README.md:3-6,27-43` は Windows 11 / RTX 4080 Laptop + Thunderbolt RTX 3090 / IQ2_XS の構成を記載するが、測定対象は upstream commit `6f32ec070f23ced9f50e704d854d775da52591ab` の prototype である。同報告の `:105-106` では prototype 時の変数名も `STRATA_ARENA_RELEASE` と記録されているため、測定値を本調査対象 commit の `STRATA_FILE_RELEASE` による現行コードの実測値とは扱わない。

## 根拠

- `engine/src/core/expert_source.cpp:3933-3982` — Windows guard、環境値の完全一致判定と static cache、mapping 条件、ページ範囲処理、失敗ログ、非 Windows の no-op。
- `engine/sycl/src/core/expert_source.cpp:1609-1659` — SYCL 実装の同じ判定と処理。
- `engine/src/program/generate.cpp:15208-15221,15873-15881,20520-20529`、`engine/sycl/src/program/generate.cpp:8810-8829,9319-9326,11360-11365` — GPU 転送・refill 完了後の release 呼び出し例。
- `engine/include/strata/core/expert_source.hpp:971-973`、`engine/sycl/include/strata/core/expert_source.hpp:567-569` — API コメント上の Windows opt-in と対象。
