# `STRATA_EXPERIMENTAL_GFX1103`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。Strata 所有コードを対象とし、外部 ROCm / HIP ライブラリや GPU ドライバー自身の環境変数動作は扱わない。

## 役割

`setup.py` で、通常は未対応として扱う AMD `gfx1103`（Ryzen 7040 / 8040 世代の Radeon 780M / 760M / 740M iGPU）を実験的な HIP GPU 候補に加える opt-in 変数。有効にすると、setup はこの GPU を Strata の AMD backend の対象に含め、統合メモリとして扱い、Linux ではこの GPU 用設定に `STRATA_NO_ARENA_THP=1` を追加する。gfx1103 向けエンジンコードを追加するコンパイルフラグではなく、setup の GPU 選定・ビルド対象決定を変える。

## 値と判定

`setup.py` の import 時に `os.environ.get("STRATA_EXPERIMENTAL_GFX1103") == "1"` を一度評価する。文字列が正確に `1` のときだけ有効で、空文字、未設定、`01`、`true`、`1 ` などはすべて無効。数値変換、空白除去、大文字小文字変換はしない。setup の同一プロセス内では `GFX1103_OPT_IN` に保持され、そのプロセスの環境を後から変更しても再評価しない。

| 値 | `GFX1103_OPT_IN` | setup 上の gfx1103 |
|---|---:|---|
| 未設定、空文字、`1` 以外の任意の文字列 | false | `AMD_ARCHS` に含めず、通常は非対応として拒否 |
| `1` | true | `AMD_ARCHS` に含め、他の条件も満たせば対応候補にする |

根拠: `setup.py:1841-1844,2138-2144`。

## 有効になる条件

- AMD HIP backend を使う setup 経路で、検出 GPU のアーキテクチャが正確に `gfx1103` であること。setup はこの変数と無関係に GPU を検出し、値が無効なら `amd_problem()` が「not supported」と判定する。値が有効なら `gfx1103` は `AMD_ARCHS` の一員となる。
- Linux では選択したアーキテクチャを `-DCMAKE_HIP_ARCHITECTURES` に渡してエンジンをローカルビルドする。CMake 側は gfx1103 を「builds, but it is not validated on a real card yet」と警告し、受理する。HIP backend の gfx11 WMMA 対象リストに gfx1103 はなく、portable path となる（`cmake/hip_backend.cmake:15-35`; `docs/STRIX_HALO.md:18-19`）。
- Windows では setup が gfx1103 の統合メモリ扱いと AMD 対象判定を行える一方、setup の表示は「This GPU has no ready-made Windows engine」と明記している。変数だけで Windows 用エンジンが提供されたり、Windows 上で gfx1103 向けエンジンをビルドできたりするわけではない（`setup.py:2012-2014`）。
- `STRATA_ADAPT_*` 等の GPU 実行時変数とは別に、Linux 上で setup が選択 GPU を gfx1103 と認識し、この opt-in が有効な場合には、生成する実行設定の env に `STRATA_NO_ARENA_THP=1` を追加する（`setup.py:5690-5702`）。

## 実行時の詳細

環境変数はエンジンの実行時には読み取られず、`setup.py` のプロセスで判定される。setup の import 時に決まった `GFX1103_OPT_IN` は、次の処理に使われる。

1. `AMD_ARCHS` に `gfx1103` を条件付きで追加する。`amd_problem()` はこのリストで GPU の対応可否を決めるため、gfx1103 は通常拒否され、opt-in 時にだけ AMD backend の候補になる（`setup.py:1843-1844,2138-2144`）。
2. `amd_apply_uma()` は、既に UMA として処理されていない gfx1103 について、専用 VRAM の carve-out と GTT（取得できない場合は RAM の半分）から共有メモリを作り、OS 用 `UMA_OS_LEFT_GB` を残す上限で `uma`, `dedicated_gb`, `shared_gb`, `vram_gb` を更新する。この値は setup の GPU メモリ表示や後続のメモリ見積もりに使われる（`setup.py:1936,1950-1964,2134`）。
3. UMA の gfx1103 では setup が Radeon 780M 系向け注記を出す。注記は実験的であり、実機検証済みではないと説明する。Linux で共有メモリが RAM の 75% より少ない場合は、GTT プールの警告も出す（`setup.py:2006-2019,2022-2028,5067-5069`）。
4. Linux で gfx1103 を HIP backend として設定すると、setup が生成する設定の `env` に `STRATA_NO_ARENA_THP=1` を追加する。ソースコメントは、transparent huge pages が pinned expert arena を移動させた際の KFD queue eviction（GPU reset）を避ける目的としている。この代入は setup が作る設定に対するものであり、`STRATA_EXPERIMENTAL_GFX1103` 自体をエンジンへ渡す処理ではない（`setup.py:5690-5702`）。

## 文書との照合・制限

`docs/AMD_HIP.md:68-69` と `docs/STRIX_HALO.md:6-8` は、gfx1103 を通常の setup 対応対象外として列挙する。一方、HEAD の `setup.py` には、この変数を正確に `1` とした場合の実験的な例外がある。したがって docs の「not supported」は標準状態の説明として読み、現在のソースには opt-in の経路があると区別する。`docs/STRIX_HALO.md:18-19` のとおり gfx1103 は WMMA kernel の対象アーキテクチャではなく portable path を使う。

setup のソースコメントは Ryzen 7 255 の1台で測定したとするが、ここでは条件付きの環境変数挙動の根拠に限り、速度や性能の数値は記載しない。`docs/DETAILS.md:239-245` にある Radeon 780M の I/O prefetch 測定は別の機能・設定（`STRATA_IO_PREFETCH` 等）の測定であり、この変数の効果を示す測定ではない。実機での gfx1103 検証が済んだとは確認できない。

## 根拠

- `setup.py:1841-1844` — opt-in の定義と AMD 対応アーキテクチャへの追加。
- `setup.py:1930-1934,1950-1964` — gfx1103 の識別名・UMA 情報の計算。
- `setup.py:2138-2144` — 検出 GPU の対応可否。
- `setup.py:2006-2028,5062-5069` — setup の gfx1103 注記と表示。
- `setup.py:2640-2679` — 対象 arch を HIP build に渡す経路。
- `setup.py:5690-5702` — Linux gfx1103 用の生成環境設定。
- `cmake/hip_backend.cmake:13-35`, `docs/STRIX_HALO.md:18-19`, `docs/AMD_HIP.md:68-71` — gfx1103 の未検証・portable kernel・通常の未対応扱い。
