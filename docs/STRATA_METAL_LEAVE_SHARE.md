# `STRATA_METAL_LEAVE_SHARE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリとドライバーの環境変数動作は対象外。

## 役割

Metal エンジンが SSD から routed experts を読む streaming mode で、arena とプロセスの全体 footprint に適用する RAM 上限を計算するとき、64 GB 以上の Mac で macOS とファイルキャッシュ用に残す RAM 比率を指定します。初期値は `0.40` です。resident pack の上限計算には使いません。

## 値と判定

`Window::stream_arena()` が環境変数の存在を調べ、設定されていれば値を `std::atof()` で `double` に変換します。数値全体の検証や範囲制限はありません。

| 入力 | `leave_share` に入る値 | `footprint_cap()` での扱い |
|---|---:|---|
| 未設定 | `-1`（構造体の初期値） | `kLeaveShare` の `0.40` を使用 |
| 空文字、数値に変換できない文字列 | `0`（`atof` の変換結果） | 0 を指定値として使用 |
| `0.25` | `0.25` | 0.25 を指定値として使用 |
| `-0.2` | `-0.2` | 0 未満なので初期値 `0.40` に戻る |
| 数値の後ろに文字が続く文字列 | 数値として読めた先頭部分 | 変換結果が 0 以上ならその値を使用 |

したがって `0` は「未設定」ではなく、比率項を無効にする明示値です。小数点表記の数値として解釈され、`1` 超などの範囲外値も clamp されません。`atof()` のため、変換失敗を検出してエラーにしたり、別の値に fallback したりする処理もありません。根拠: `metal/src/engine/window.cpp:1164-1167`, `metal/src/engine/arena_budget.h:36-47,84-89`。

## 有効になる条件

- Metal engine の `Window::init()` が `ExpertStream::wanted()` を通じて streaming を選んだときに限り、arena の計画でこの値が使われます。streaming は `STRATA_METAL_STREAM=1` で明示的に選ぶか、同変数が未設定または `1`/`0` 以外で、モデルの重みと付随メモリが resident 上限に収まらない場合に自動選択されます。`STRATA_METAL_STREAM=0` なら streaming になりません（`metal/src/engine/window.cpp:425-435`, `metal/src/engine/stream.cpp:33-48`）。
- `footprint_cap()` は RAM が `64 * 1e9` bytes 以上の場合にだけ `leave_share * phys` を残量計算へ加えます。未満の場合、`STRATA_METAL_LEAVE_SHARE` を設定してもこの比率は無視されます。
- 64 GB 以上でも、実際に残す量は比率だけでは決まりません。`max(keep, leave_share * phys, filecache_min + 12 GB)` を使い、file-cache 下限の取得に失敗した場合はその項を 0 として、最終上限を `min(working_set, phys - leave)` にします。`STRATA_METAL_KEEP_FREE_GB` は `keep` の既定値 `max(7 GB, 15% of RAM)` を上書きできますが、比率項などとの最大値計算は残ります（`metal/src/engine/arena_budget.h:75-89`）。
- `STRATA_METAL_ARENA_GB` が 0 以上に変換されると arena サイズを直接指定する分岐が優先され、自動 arena サイズの計算や縮小・段階的な空きメモリ確認を行いません。その場合も footprint cap の表示・超過判定にはこの比率が反映されます（`metal/src/engine/arena_budget.h:112-117,144-158`; `metal/src/engine/window.cpp:1164-1169,1182-1192`）。

## 実行時の詳細

環境変数は `stream_arena()` の呼び出しごとに読み直され、関数内のローカルな `ArenaMem` に格納されます。streaming arena が未準備の初回 decode/prompt 経路などから計画時に呼ばれます。環境値自体を static cache する処理はありませんが、arena が `ready()` になった後はこれらの呼び出し条件を通らないため、実行中に環境を変更しても既に確定した arena は再計画されません（`metal/src/engine/window.cpp:1016-1019,1127-1169,2021,2115`）。

起動時には `planned resident footprint ... cap ...` の行に計画値と cap が出力されます。arena 充填後には実際の process footprint と cap を出し、実 footprint が cap を超えた場合は ` - OVER THE CAP` を付けます。`STRATA_METAL_ARENA_GB` が cap を超える場合も値は指定どおり維持され、その選択で Mac がメモリ不足になる可能性を示す警告文が計画ログに付加されます（`metal/src/engine/window.cpp:1182-1192,1210-1216`）。

## 根拠

- `metal/src/engine/window.cpp:1127-1169` — streaming arena の初期化、RAM 状態取得、環境変数読み取り、cap を使う予算計算。
- `metal/src/engine/arena_budget.h:36-47,72-97,112-158` — 初期値、既定比率、RAM サイズ条件、cap と arena 予算・縮小・充填規則。
- `metal/src/engine/stream.cpp:33-48` — streaming の明示選択と自動選択。
- `docs/MAC.md:183-200` — `STRATA_METAL_LEAVE_SHARE=0.4` を streaming 用の測定スイッチとして記載。説明はコード上の適用条件と一致します。性能値の測定はこの変数の単独効果として示されていないため、ここでは性能上の主張をしません。
