調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。
サーバーのバッチ入場（`BGEN` / `BGENI`）で、最後の prompt 部分の末尾と、その入場で生成する最初の token を一つの verify window にまとめる opt-in です。通常は prompt の最後の token までを読み終えた後に、最初の生成 window を別に実行します。まとめると window の処理を一度に行えます。

対象は `src/program/generate.cpp` のサーバー要求処理です。コメントでは、各 row が通常の window と同じ計算を行い、最後の prompt row の次の row が最初の生成位置、その履歴と Philox draw を使うため token と状態を保つ設計とされています。実装ではまとめた window の prompt row を通常の prompt window と同様に commit し、最終 row の出力だけを生成 token として扱います。これはコード上の設計説明であり、本調査では実行比較をしていません。
判定結果は関数内の `static const bool` に保存されます。値全体の parse や数値変換はなく、`getenv()` が非 null で、先頭文字が `'0'` でなければ有効です。
| 環境値 | 判定 |
| unset | 無効（既定） |
| 空文字 | 有効（設定済みで先頭文字は `\0`） |
| `0`, `0anything` | 無効 |
| `1`, `true`, `false`, `2`, `anything` | 有効（先頭文字が `0` 以外） |

大文字小文字、空白、残りの文字列は検査しません。読み取りはプロセス起動時ではなく、`admit_merge_first_env()` の初回呼び出し時です。初回評価後にプロセス環境を変更しても反映されません。通常の `GEN` も含む window 対象部分で helper が呼ばれうるため、最初の評価がバッチ入場そのものとは限りません。
根拠: `src/program/generate.cpp:186-197,13926`。
値が有効でも、次をすべて満たす場合に限り merge します。
- 対象要求がバッチ入場である（`admit_slot >= 0`）。
- 要求の `max_new` が 1 で、batch MTP と pipeline windows を使っていない。
- 最後の prompt part が verify windows を通る。`windows_ok()` は `--short-read` 相当の `req_short_read` を超える長さの part を拒否し、embedding row がある part も拒否する。要求ごとの `STRATA_PIPELINE_SWITCH` が `short_read=` を設定する場合はその値が使われる。
- 最後の part の終端が prompt 終端であり、turn/root/message/pin checkpoint 境界と重ならない。
- 画像入力、KV growth (`kvg.on`)、peer device、remote cache / remote expert、filesystem swap がない。
- `STRATA_LOGPOS` が unset。
- `host_res` が空でなく、pending work がなく、resident table に負値の expert entry がない。
- 全 stage の verifier で `ar_live()` が true である。これは refresh 後に `all_resident_ && !ar_off_` であることを表し、各 stage の全 expert が resident で、all-resident 経路が off でないことを要求する。
- 最小 stage `max_t` が 2 以上。
いずれかを満たさないと `merge_at` は `-1` のままで、従来どおり prompt の読み取りと最初の生成 window を分けます。値が有効でも feature 全体を無条件に有効化するわけではありません。
根拠: `src/program/generate.cpp:12917-12923,13888-13908`; `include/strata/core/verify.hpp:179-181,459-462`。
最後の part が window 対象のとき `merge_from()` が条件を確認し、`merge_at = max(a0, n - mt)` を返します。ここで `mt` は `kVerifyMaxT` と各 stage の `max_t()` の最小値です。prompt 読み取り側は `merge_at` より前までを処理し、`merge_at` 以降の最後の最大 `mt` 個の prompt token を残します。trace が有効な場合、実際に merge したとき stderr に `strata trace: the first window takes the last %lld prompt tokens` を出します。
最初の decode loop は `merge_T = n - merge_at` を window 長に使い、prompt の末尾 token 群を window に入れます。merged window は prompt row を commit し、最終 row の出力のみを最初の生成 token として出力します。まとめた prompt rows は decode draft の件数に含めません。`STRATA_TRACE` の admission trace による処理時間の計測もありますが、環境変数による性能向上を示す測定値は参照したコード・`docs/BATCHING.md` にありません。
根拠: `src/program/generate.cpp:13926-13939,14008-14016,14724-14731,14978-15014`。関連する短い説明: `docs/BATCHING.md:110-121`。
- 値の読み取りと変換: `src/program/generate.cpp:186-197`。
- window eligibility: `src/program/generate.cpp:12917-12923`。
- merge 条件と位置計算: `src/program/generate.cpp:13888-13908`。
- prompt read / trace: `src/program/generate.cpp:13910-13939`。
- merged window の生成 loop と出力: `src/program/generate.cpp:14008-14016,14724-14731,14978-15014`。
- all-resident gate: `include/strata/core/verify.hpp:179-181,459-462`。
- 設計資料との照合: `docs/BATCHING.md:110-121` は opt-in で「admission reads its last prompt tokens and its first token in one window (all experts resident only)」と記載しており、上記の実装条件と整合します。
