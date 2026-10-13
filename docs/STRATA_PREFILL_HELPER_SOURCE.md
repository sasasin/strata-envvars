# `STRATA_PREFILL_HELPER_SOURCE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata serve` の prompt prefill が読む expert blob について、helper GPU の VRAM cache に現在ある blob を、モデルファイルの代わりにその cache から host staging buffer へコピーします。prefill の計算は従来どおり主 GPU で行います。helper にない blob は元の `ExpertSource` に渡されるため、通常の file read、batched read、pinned RAM copy の扱いは維持されます。

これは opt-in で、既定では無効です。有効でも以下の実行条件を満たさなければ source は切り替わりません。コード上の読み取りは `src/program/generate.cpp` の1か所です。

## 値と判定

値全体の比較ではなく、`std::atoi(hv) != 0` で判定します。環境変数が未設定なら条件は偽です。空文字や整数として読めない文字列は `atoi` が0を返すため無効です。先頭の整数部分が0でない値（例: `1`, `2`, `-1`, `1junk`）は値条件を通ります。したがって「文字列が `1` と完全一致すること」は必要ありません。変換結果が `int` の範囲外の場合の扱いは、この呼び出し側では検査していません。

| 環境変数の値 | 値条件 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（`atoi` が0） |
| `0`、`00`、数値に変換できない文字列 | 無効 |
| `1`、`2`、`-1`、`1junk` など、`atoi` が0以外を返す値 | 有効候補。実行条件も必要 |

根拠: `src/program/generate.cpp:6951-6956`。

## 有効になる条件

値条件に加え、source wrapper は次をすべて満たすときだけ作られます。

- `serve` 経路である。
- `srcp` が有効な expert source を指す。
- `multi_gpu` が偽で、`stages` が空。つまり layer split 等の複数 GPU stage を使わない。
- `o.batch <= 0` である（batch slots を使わない）。
- `drive.d.remote_count` が1以上で、helper GPU が構成されている。

条件が不足した場合、環境変数を設定しても helper source は作られず、起動時の有効ログも出ません。server はこの経路で prompt を serial に処理し、prompt read 中 helper GPU が idle であるという実装コメントが、helper cache を読む前提です。CUDA の `RemoteExperts` を使う経路であり、同名の読み取りは SYCL 実装には見つかりません。

## 実行時の詳細

環境変数は `serve` の初期化中に読み取られ、`RemotePrefillSource` が作られるかどうかが決まります。その source を `Prefill::init` に渡し、serve の各 prompt read に使います。読み取り箇所は static cache ではありませんが、この分岐自体は serve source の初期化時に一度実行されます。server 実行中に環境変数を書き換えても、既に構築済みの source の有無は変わりません。根拠: `src/program/generate.cpp:6946-6957,7284-7287`。

`RemotePrefillSource` は要求ごとに helper の `holds(layer, expert)` を調べます。helper にある blob は stager の `copy_blob(s)` 経路へ誘導され、helper ごとの専用 non-blocking CUDA stream で device-to-host copy を発行して同期します。複数 blob は helper ごとにまとめてコピーします。helper の cache は request 間で変化し得るため、この wrapper は blob を別途 cache せず、各回の現況を照会します。根拠: `include/strata/core/remote_experts.hpp:104-153`, `src/core/remote_experts.cpp:349-379,381-449`。

helper に blob がない場合や helper copy が失敗した場合、その blob は元の source から取得します。失敗時は `prefill: a helper cache read failed (%s); the file source fills that blob instead` を stderr に最大1回出します。fallback の source copy 自体が失敗すると、prefill stager は失敗した旨を stderr に出し `abort()` します。正常な request 終了時は `strata serve: prefill helper source: %lld blobs / %.1f MiB taken from a helper's cache in this request` を stderr に出し、その request で helper cache から取った量を示します。wrapper を使わない場合、このログは出ません。根拠: `src/core/remote_experts.cpp:451-455`, `src/prefill/prefill.cpp:517-519`, `src/program/generate.cpp:12539-12545`。

## 文書との照合

`docs/SECOND_GPU.md:70-74` は helper GPU が decode を担当し、prompt prefill は CUDA0 で行うと説明しています。今回確認した opt-in は prefill の計算先を変えず、helper VRAM cache から prompt 用 blob を読む source を追加するものなので、この説明と矛盾しません。同文書と `docs/DETAILS.md` には、この変数や helper cache からの prompt read を直接説明する記載は見つかりませんでした。性能値や token 同一性の測定根拠も確認できなかったため、ここでは性能効果を断定しません。

## 根拠

- 環境変数の判定、適用条件、起動ログ: `src/program/generate.cpp:6941-6957`
- prefill source への設定: `src/program/generate.cpp:7284-7287`
- wrapper の fallback / helper copy 方針: `include/strata/core/remote_experts.hpp:104-153`
- helper VRAM から host への copy と fallback: `src/core/remote_experts.cpp:349-449`
- 失敗時ログ: `src/core/remote_experts.cpp:451-455`, `src/prefill/prefill.cpp:517-519`
- request ごとの利用量ログ: `src/program/generate.cpp:12539-12545`
- helper GPU と prompt prefill の説明: `docs/SECOND_GPU.md:70-74`
