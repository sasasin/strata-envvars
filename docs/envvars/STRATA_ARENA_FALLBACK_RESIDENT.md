# `STRATA_ARENA_FALLBACK_RESIDENT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

expert arena の読み込みが RAM 不足でできず、ファイル読み込みへ切り替わるとき、静的 expert profile があれば、profile 上位の expert を可能な範囲で RAM に保持する resident RAM mode へ自動で切り替えます。この変数を `0` で始める値にすると、その自動切り替えを止め、通常の file source のままにします。`src/program/generate.cpp:7321-7343`。

この変数は arena 不足時の自動選択だけを制御します。値を読んだ時点で RAM を確保したり、arena 不足そのものを回避したりはしません。

## 値と判定

値全体の parse はせず、`getenv()` の結果が存在し、先頭文字が `0` かだけを判定します。空文字は設定済みですが先頭文字が `\0` なので、自動切り替えを止めません。`0`, `0anything` は止め、`1`, `false`, `anything`, 空文字、未設定は止めません。`src/program/generate.cpp:7075`。

| 値 | 自動 resident fallback の判定 |
|---|---|
| 未設定 | 有効（他の適用条件を満たす場合） |
| 空文字 | 有効 |
| 先頭文字が `0` | 無効 |
| それ以外 | 有効 |

`atoi`、数値範囲検査、大文字小文字変換はありません。判定結果は起動処理中に一度ローカル変数へ格納され、同じ起動処理の arena/file 再試行ループで使われます。プロセス起動後に環境を書き換えた場合の再評価はありません。`src/program/generate.cpp:7074-7075,7089`。

## 有効になる条件

次の条件が揃ったときだけ、この判定が使われます。

- arena source を選び、arena の open が RAM 不足で失敗する。ほかの open エラーではこの fallback 分岐に入りません。`src/program/generate.cpp:7316-7327,7345-7348`。
- `STRATA_ARENA_RAM_FALLBACK` による file source への切り替えが許可されている。既定では許可されますが、手動指定の `--ple-io ram` または `--shared-expert-arena` があると禁止されます。変数が空でない場合は `atoi(value) != 0` で判定されます。`src/program/generate.cpp:7072-7073`; `include/strata/core/ple_residency.hpp:65-72`。
- `--expert-profile` による profile があり、すでに `o.resident_cpu_experts` が有効ではなく、この環境変数の先頭文字が `0` ではない。`src/program/generate.cpp:7333-7340`。

したがって未設定は自動切り替えを許しますが、静的 profile がなければ切り替えは行われません。`0` を指定した場合でも arena の RAM fallback 自体は止めず、file source による起動を続けます。既に `--mmap-experts` と resident RAM mode を指定した実行は arena 不足からの自動選択経路ではなく、この変数の対象外です。`src/program/generate.cpp:3644-3669,7091-7101,7333-7343`。

読み取りと分岐に OS/backend/build macro の条件はありません。一方、fallback 後の headroom は Windows では既定 8 GiB、その他では 4 GiB で、`STRATA_RESIDENT_HEADROOM_GIB` や `--ram-keep-gib` が関係します。RAM copy の予算は利用可能 RAM から headroom を引いて決まり、headroom を超える余裕が 1 GiB 以下なら予算は 0 です。`src/program/generate.cpp:7076-7087,7334-7339`; `include/strata/core/ple_residency.hpp:91,108-117`。

## 実行時の詳細

arena が RAM 不足で開けないと、stderr に `strata generate: not enough RAM for the expert arena (...)` と出し、`--mmap-experts` と同等の file source を試します。自動 resident fallback が選ばれた場合は `o.resident_cpu_experts`、`o.resident_pin`、`o.resident_soft` を有効にし、残す headroom と RAM budget を設定します。`src/program/generate.cpp:7321-7343`。

その後、source はモデルファイルを開き、GPU cache にない expert の RAM copy を `pin_cache_complement()` で構築します。profile 順で保持を試し、全体が入らなくても可能な範囲の保持を試す soft mode です。実際に保持できた場合は `strata generate: resident RAM mode: ...` が出ます。全体も部分的な resident copy も確保できない場合は `strata generate: WARNING: the resident RAM mode does not fit (...)` が出て、GPU cache にない expert は `--mmap-experts` と同様にモデルフォルダーから読みます。`src/program/generate.cpp:9903-9921,9964-9984`。

file source 自体を開けない場合、起動処理は resident fallback の状態を戻して arena を従来どおり再試行します。そのとき `strata generate: the experts cannot be read from the file either (...): loading the expert arena as before, short of RAM` を出します。`src/program/generate.cpp:7101-7113`。

`STRATA_ARENA_FALLBACK_RESIDENT` の完全一致検索では、実行時の読み取りは `src/program/generate.cpp:7075` のみでした。`src/program/generate.cpp:7331` はコメント、`docs/DETAILS.md:764` は説明文です。`sycl/src/program/generate.cpp` にこの変数の読み取りはなく、SYCL 実装で同じ制御が働くとは確認できません。`src/program/generate.cpp:7075,7331`; `docs/DETAILS.md:764`。

## 根拠

- 値の判定と評価位置: `src/program/generate.cpp:7072-7089`。
- RAM 不足時の file fallback と resident 切り替え条件: `src/program/generate.cpp:7316-7348`。
- file source が開けない場合の arena 再試行: `src/program/generate.cpp:7101-7113`。
- resident copy の構築、部分保持、ログと非致命的 fallback: `src/program/generate.cpp:9903-9921,9964-9984`。
- fallback の可否、headroom と budget の計算: `include/strata/core/ple_residency.hpp:65-72,91,108-117`。
- 関連説明との照合: `docs/DETAILS.md:749-764` は、profile がある場合に上位 expert を RAM に保持し、`STRATA_ARENA_FALLBACK_RESIDENT=0` で通常の file source を維持すると説明しており、現行分岐と一致します。
