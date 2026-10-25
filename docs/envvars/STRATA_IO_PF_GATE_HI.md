# `STRATA_IO_PF_GATE_HI`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有ソース。外部ライブラリや OS の内部動作は対象外。

## 役割

Linux の mmap ファイル tier で I/O prefetch を有効にしたとき、decode gate が閉じた状態から再び開くために必要な、ファイル tier の expert bytes に対する page cache の空き容量比を指定します。ゲートがすでに開いている場合に閉じる閾値は `STRATA_IO_PF_GATE_LO` が決めます。この上下の閾値に差を設けることで、開閉の境界にヒステリシスを持たせます。

## 値と判定

`FileExpertSource::set_io_prefetch()` の中で、環境変数が設定されている場合に `std::atof()` で数値へ変換し、`gate_lo_` 以上、`1.0` 以下に clamp します。`gate_lo_` は先に読み取られる `STRATA_IO_PF_GATE_LO` の値（既定 `0.55`）です。

| 入力 | `gate_hi_` の結果（`gate_lo_` が既定 `0.55` の場合） |
|---|---:|
| unset | 既定値 `0.65` |
| 空文字、数値で始まらない文字列、負値、`0.55` 未満 | `0.55` |
| `0.8`、または `0.8tail` | `0.8`（数値として読める先頭部分） |
| `1` または `1` より大きい値 | `1.0` |

文字列全体の妥当性検査はなく、`atof()` が変換できない文字列は `0` として扱われてから下限値へ clamp されます。明示的な空文字も unset とは異なり、`atof("")` の結果 `0` が下限値へ clamp されます。`STRATA_IO_PF_GATE_LO` が別途指定されていれば、その clamp 下限を使います。

## 有効になる条件

- `set_io_prefetch(true, ...)` の Linux 実装が実行される必要があります。生成経路では mmap の file tier が対象で、`STRATA_IO_PREFETCH` が有効、または Linux の既定条件が成立した場合に setup されます。既定では GGUF をそのまま読む経路、または `experts.bin` の expert bytes に対して page cache の空きが既定の 55% 以上ある経路で I/O prefetch が有効になります。
- setup が direct/unbuffered 読み取りの経路でない必要があります。Windows/macOS ではこの Linux 専用コードは実行されません。
- `STRATA_IO_PF_GATE=0` などで gate 自体を無効にすると、この値を読み取っても gate の開閉には使われません。gate は I/O prefetch setup 時に既定で有効になり、`STRATA_IO_PF_GATE` が空でない場合は `atoi(value) != 0` の結果で上書きされます。

## 実行時の詳細

値は各 `FileExpertSource` の I/O prefetch setup 時に読み取られ、リクエストや decode window ごとには読み直されません。そのオブジェクトの setup 後に環境を変更しても閾値は変わりません。

ゲートは初期状態で開いています。`gate_capacity()` は decode window ごとに呼ばれ、16 window ごとに page cache の空き容量比を調べます。ゲートが開いているときは比率が `gate_lo_` 未満になると閉じます。閉じているときは比率が `gate_hi_` を**超えた**場合に開きます（等しいだけでは開きません）。未知または 0 の容量情報なら、その回は状態を変えません。

閉じると decode の demand read で未キャッシュ分を `pread` する経路と router の read-ahead が止まり、decode は従来の mapping 読み取りに戻ります。router の read-ahead は閉状態で深さを 1 にし、mmap を使う経路では `madvise(MADV_WILLNEED)` による従来の warm 処理へ戻ります。ゲートの開閉状態や cache room 比は `strata serve` の request I/O 統計で `decode gate: cache room ...`, `open` / `closed`, closed window 数、flip 数として stderr に出ます。

## 根拠

- `include/strata/core/expert_source.hpp:1034-1045`: gate 関連の初期値。`gate_hi_` の既定値は `0.65`、gate は初期 open。
- `src/core/expert_source.cpp:1114-1156`: Linux の setup 条件、`STRATA_IO_PF_GATE_HI` の唯一の読み取り、`atof` と clamp の順序。
- `src/program/generate.cpp:5655-5689`: Linux file tier での I/O prefetch 起動条件と起動ログ。
- `src/core/expert_source.cpp:1751-1766, 1897-1901, 1971-2004, 2976-2990, 3276-3292`: decode read / read-ahead でのゲート適用、cache room 比、16 window ごとの判定と閾値比較。
- `src/core/expert_source.cpp:3175-3178`, `src/program/generate.cpp:15424-15429`: 閉状態での lookahead 深度と request 統計ログ。
- `docs/DETAILS.md:272-298`: gate の設計説明では既定の閉じ側 0.55、開き側 0.65 と 16 window ごとの判定を記載しています。同節の速度値は I/O prefetch 等を含む機能一式の比較であり、`STRATA_IO_PF_GATE_HI` 単独の効果を測った値ではありません。
