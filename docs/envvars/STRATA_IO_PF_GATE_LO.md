# `STRATA_IO_PF_GATE_LO`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux の file tier I/O prefetch に付属する decode gate が、開いている状態から閉じるかどうかを決める下限しきい値です。判定対象は、ページキャッシュに使えるメモリ量を file tier の expert データ総量で割った比率です。初期値は `0.55` です。

この値は io prefetch の起動可否を直接決めません。起動時の既定有効判定には、`experts.bin` ではない file tier について `cache_room_ratio() >= 0.55` という独立した固定値があります。`STRATA_IO_PF_GATE_LO` は、prefetch が起動して gate が有効な場合の、その後の decode 中の gate 判定に使われます。

## 値と判定

| 入力 | `gate_lo_` への値 |
|---|---:|
| 未設定 | `0.55` |
| 空文字 | `0.0` |
| 数値文字列 | `std::atof` で変換し、`[0.0, 1.0]` に clamp |
| 数値に変換できない文字列 | `0.0`（`atof` の変換結果） |
| 負数 / 0 未満 | `0.0` |
| 1 より大きい数 | `1.0` |

文字列全体の厳密な数値検証はしません。`atof` が認識する先頭の数値部分が使われるため、たとえば `0.7tail` は `0.7` として扱われます。空白を含む数値も `atof` の規則で変換されます。

相互作用する `STRATA_IO_PF_GATE_HI` も設定されていれば、後から読み取られ、`gate_hi_` は `[gate_lo_, 1.0]` に clamp されます。したがって `HI` が未設定の既定値 `0.65` より `LO` が大きければ、実際の再開しきい値は `LO` まで引き上げられます。

## 有効になる条件

- この読み取りと gate の実装は Linux 向け `FileExpertSource::set_io_prefetch()` にあります。
- `set_io_prefetch(true, ...)` が実際に初期化を完了しなければ値は読み取られません。`STRATA_IO_PREFETCH=0` などで prefetch が無効な場合や、file の open に失敗するなど初期化が途中で戻る場合、この変数は効果を持ちません。
- io prefetch の初期化時に gate は既定で有効です。別変数 `STRATA_IO_PF_GATE` が空でない値として設定されている場合は `atoi(value) != 0` で上書きされます。`STRATA_IO_PF_GATE=0` なら gate は無効になり、`STRATA_IO_PF_GATE_LO` は使われません。
- gate は decode window の処理に適用されます。ソースは新しい window ごとに容量判定関数を呼びますが、容量比の再計算は16 windowごとです。prompt 経路はこの decode gate の対象外です。

## 実行時の詳細

初期化時に `getenv` で値を読み、`std::atof` と `std::clamp` の結果を `FileExpertSource` インスタンスの `gate_lo_` に保存します。以後、環境変数を変更しても、そのインスタンスのしきい値は更新されません。

gate 容量判定では、cgroup v2 の制限が取得できる場合は cgroup と祖先のうち最も小さい空き量を使い、そうでない場合は `/proc/meminfo` の `MemAvailable` を使います。これを expert データ総量で割り `gate_ratio_` とします。値が不明（総量または空き量が0）の場合は gate 状態を変えません。

開いている gate は `gate_ratio_ >= gate_lo_` の間開いたままになり、下回ると閉じます。閉じている gate は `gate_ratio_ > gate_hi_` になって再開します。閉じた状態では decode の pread/read-ahead を抑え、look-ahead の深さも1にします。ほかに、open 状態で16 window内の read-ahead が128 MiB未満、または有用率が `STRATA_IO_PF_GATE_USEFUL` の下限を下回った場合にも gate は閉じます。この理由で閉じた場合は、容量条件を満たしていても256 windowごとの probe まで再開しません。

gate が有効な場合、生成側の診断出力には cache room 比、read-ahead 使用率、decode read の page-cache hit EWMA、open/closed 状態、閉じた window 数と切替回数が出ます。`STRATA_IO_PF_GATE_LO` 固有のログはありません。

## 根拠

- `src/core/expert_source.cpp:1114-1155` — Linux I/O prefetch 初期化、gate の既定有効化、`STRATA_IO_PF_GATE` と本変数の読み取り、および数値変換・clamp。
- `src/program/generate.cpp:5655-5670` — 起動時の io prefetch 判定と `set_io_prefetch()` の呼び出し。
- `include/strata/core/expert_source.hpp:995-1026,1034-1043` — gate の役割、初期値、Linux 既定起動条件。
- `src/core/expert_source.cpp:1903-1917,1920-1979,1980-2004,3290-3292` — decode window の計測、空き容量比、しきい値比較と再評価周期。
- `src/core/expert_source.cpp:1081-1083,1750-1757,2974-2983,3175-3178` — gate 状態による read-ahead、decode demand pread、look-ahead 深度への反映。
- `src/program/generate.cpp:15424-15429` — gate 状態の診断ログ。
- `docs/DETAILS.md:282-298` — Linux file tier gate の説明と測定記録。記載測定は gate しきい値 `0.55` / `0.65` を含む file-tier 機能全体の比較であり、`STRATA_IO_PF_GATE_LO` 単独の性能差を測ったものではありません。
