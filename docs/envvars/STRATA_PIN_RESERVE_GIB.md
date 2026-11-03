# `STRATA_PIN_RESERVE_GIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Linux の resident RAM expert copy を page-lock する際、段階的に確保する各ステップの後に残す空き RAM を GiB 単位で指定します。単独で page-lock を有効にする変数ではありません。`--resident-experts`、`--resident-budget-gib`、または RAM 不足時の resident fallback など、expert の RAM 補完を page-lock する経路で使われます。通常の一括 page-lock が可能な場合は、この値を残量条件として使わず、段階登録が必要な場合に使います。

## 値と判定

値は `std::atof()` で読み、その結果が正なら `GiB × 1,073,741,824` を `uint64_t` に変換します。文字列全体の検証や上限 clamp はありません。数値の後ろの文字は `atof` が解釈しないため、たとえば `1.5GiB` は先頭の数値部分 `1.5` として扱われます。整数ではなく小数も指定でき、byte に変換するとき小数部は切り捨てられます。

| 状態 | 使われる reserve |
| --- | --- |
| 未設定 | `max(headroom_bytes, 2 GiB)` |
| 空文字、数値に変換できない文字列、0、負数 | `max(headroom_bytes, 2 GiB)` |
| 正の数値（小数を含む） | 指定値を byte に変換した値 |

`headroom_bytes` は呼び出し元から渡される resident mode の headroom です。`--resident-experts` と `--resident-budget-gib` は通常 4 GiB を初期値にし、`STRATA_RESIDENT_HEADROOM_GIB` や `--ram-keep-gib` などの処理がこれを調整します。したがって変数が未設定または無効値のときの既定 reserve は通常 4 GiB 以上ですが、呼び出し元の headroom が 2 GiB 未満なら最低 2 GiB です。正の値を指定するとこの既定値に対する `max` は適用されず、指定値が使われます。

根拠: `src/core/expert_source.cpp:3785-3789`、`src/program/generate.cpp:3647-3672,3692-3700`。

## 有効になる条件

- `pin_cache_complement()` が resident expert cache complement を構築し、対象 bytes が 0 より大きいときに値を読みます。`pin` が false の場合もこの読み取り式自体は評価されますが、page-lock の分岐で reserve を使わないため挙動には影響しません。
- reserve が page-lock 判定に影響するのは `__linux__` の `pin` 経路です。Windows では `pace_reserve` の式は評価されますが、段階登録の分岐を含む Linux 専用コードがないため、この値による reserve 制御はありません。
- Linux では `STRATA_PIN_GUARD=2` が段階登録を常時選びます。`STRATA_PIN_GUARD` が 0 でなく 2 でもない場合は、現在の空き RAM が補完全体の bytes と reserve の合計を下回るとモデルファイルの cache を解放し、再計測後も合計に足りなければ段階登録します。`STRATA_PIN_GUARD=0` は通常この自動選択を止め、一括 page-lock を試みます。ただし NUMA split 配置が有効なら、guard が 0 でも cache を解放して段階登録します。
- 一括 page-lock が拒否された場合にも resident memory への fallback があり得ますが、`STRATA_PIN_RESERVE_GIB` がその後の段階登録ループで使われるのは `paced` が true の場合だけです。

根拠: `src/core/expert_source.cpp:3785-3818,3836-3859,3912-3927`。

## 実行時の詳細

値は complement 構築中、`bytes > 0` の処理に入るたびローカル変数として読み取られます。`STRATA_PIN_RESERVE_GIB` 自体は `static` cache されていません。resident mode が全体失敗後に soft fallback を試すと `pin_cache_complement()` がもう一度呼ばれる場合があり、その場合も再読込されます。一方、`STRATA_PIN_GUARD` は同じ関数内で `static` に一度だけ読み取られます。CLI 引数が reserve 値を直接上書きする処理はなく、指定された正の `STRATA_PIN_RESERVE_GIB` が既定 reserve を置き換えます。

段階登録では最大 1 GiB の step ごとに空き RAM を再計測し、`available >= step + pace_reserve` の間だけページを touch します。RAM が reserve を割り込む見込みになるか空き RAM を取得できないとそこで止まり、登録範囲を expert blob の境界に切り下げて page-lock を試します。残りは resident だが pageable な領域として扱われ、コピーは CPU 経由になります。reserve が利用可能 RAM より大きいなど、step が一つも通らない場合も段階処理は停止し、全体を page-lock できなければ pageable fallback になります。この設定値だけを理由に Strata が即座に終了する分岐はありません。

段階登録の開始時には `FileExpertSource: STRATA_PIN_GUARD=2: page-locking the complement in steps` または NUMA 経路のログが出ます。RAM 条件などで全量を登録できない場合は `WARNING: only N of M GiB could be page-locked (...)` が stderr に出て、最終状態は `cache complement ready` の `resident` / `pinned` GiB 表示にも反映されます。page-lock できない範囲を含む場合の GPU copy の CPU 経由も、この警告文字列に明記されています。

根拠: `src/core/expert_source.cpp:3785-3789,3813-3829,3912-3971,4182-4186`。呼び出しと soft fallback は `src/program/generate.cpp:9903-9921`。

## 文書との照合

`docs/TROUBLESHOOTING.md:272-280` は、Linux でモデル file cache を解放して段階的に page-lock する目的、および `STRATA_PIN_RESERVE_GIB` が残す RAM を指定する点を説明しています。現行コードでは既定値は単純な `STRATA_RESIDENT_HEADROOM_GIB` ではなく、呼び出し元の `headroom_bytes` と 2 GiB の大きい方です。また、NUMA 配置時は `STRATA_PIN_GUARD=0` でも段階登録を強制します。
