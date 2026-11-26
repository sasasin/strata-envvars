# `STRATA_SLOT_CKPT_MOVE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

バッチ slot への admission で、会話の turn 境界 checkpoint を main session の `checks` から slot の `checks` へコピーせず移動するスイッチ。通常は checkpoint を複製して両方に保持するが、有効時は対象 checkpoint の所有先が slot に移る。admission 時の checkpoint 複製を避ける一方、その checkpoint は main session 側には残らない。checkpoint は token 履歴に一致する状態を復元するためのもので、slot の live state や生成 token の選択処理自体を切り替えるスイッチではない。実装は `slot_ckpt_move_env()` と serve loop の admission / restore 処理（`engine/src/program/generate.cpp`）。`engine/src/core/arch_defaults.cpp` 等が対応構成で未設定時にこの変数を `1` にする場合がある。

## 値と判定

`slot_ckpt_move_env()` は最初の呼び出し時に `std::getenv` の結果を関数内 `static const bool` に保存する。未設定 (`nullptr`) は false、設定済みなら値の先頭文字が `'0'` 以外のとき true。文字列全体の parse、数値変換、大文字小文字変換、空白除去はしない（`engine/src/program/generate.cpp:566-572`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| 環境値の読み取り | 無効 | `1`, `true`, `yes`, ` 1`, 空文字列 | `0`, `0anything` |

空文字列は設定済みで先頭文字が `'0'` ではないため有効。`false` や `no` も有効。`0` で始まる値は後続文字に関係なく無効。初回評価後に環境を変更しても、このプロセスでは cache 済みの判定が使われる（同 `generate.cpp:566-572`）。

unset 時の既定は実行条件により異なる。engine は構成に応じて serve loop の環境へ値を設定し、既に設定されている値は上書きしない。従って、明示的な空文字や `0` は自動設定を止め、判定関数にもそのまま渡る。

| engine の条件（slot 数は `o.batch`） | Strata が未設定時に行う処理 | 実効値 |
|---|---|---|
| Linux CUDA build、batch slot 2 個以上 | parallel stack の一つとして `1` を設定 | 有効 |
| HIP build、gfx1151 (Strix Halo)、Windows、batch slot 2 個以上、`STRATA_GFX1151_DEFAULTS` が `0` で始まらない | parallel defaults として `1` を設定 | 有効 |
| gfx11 discrete RDNA3 build（Linux / Windows）、batch slot 2 個以上、`STRATA_DEFAULTS` が `026` 系 token でなく、`STRATA_GFX11_DEFAULTS` が `0` で始まらない | parallel defaults として `1` を設定 | 有効 |
| 上記以外 | この変数を自動設定しない | unset のため無効 |

Linux CUDA の自動設定は `engine/src/program/generate.cpp:4410-4414` と `engine/src/core/arch_defaults.cpp:248-260`。HIP の gfx1151 条件は `generate.cpp:4287-4320`、arch defaults の条件と変数セットは `arch_defaults.cpp:240-245, 433-442`。gfx11 discrete の条件・`STRATA_DEFAULTS=026` 系 token と `STRATA_GFX11_DEFAULTS=0` による無効化は `engine/include/strata/core/gfx11_extra.hpp:27-31, 116-132` および `engine/include/strata/core/defaults_026.hpp:21-30`、適用箇所は `arch_defaults.cpp:346-355`。CUDA / HIP の setter は設定済みの環境値（`0` を含む）を保つ（`arch_defaults.cpp:253-260, 433-436`）。

## 有効になる条件

- batch admission により request が slot へ取り込まれ、slot に引き継げる checkpoint があること。環境値だけで batch 実行や slot を有効にするものではない（`engine/src/program/generate.cpp:23673-23724`）。
- checkpoint が現在の会話履歴の prefix で、画像を含まず、pinned ではないこと。移動対象は turn 境界（`turn_at`）または slot から main session に戻した checkpoint（`moved_in`）に限る。root、pinned prefix、他の共有 checkpoint は従来どおりコピーされる（同 `generate.cpp:23673-23724`）。
- prompt cache が必要な checkpoint を保持していること。slot checkpoint を他の request の resume 元に探す処理は `o.prompt_cache > 0`、live session の有効性、control vector の一致を条件とし、tainted / control vector の異なる slot は除外する（同 `generate.cpp:19291-19309`）。
- 画像を含む slot は slot checkpoint をこの cache 経路で使わない（同 `generate.cpp:19322-19341, 23692-23707`）。
- `STRATA_CKPT_POOL` が `0` でも、slot move が有効なら `CheckpointPool` は有効化される。移動で main session の checkpoint がなくなっても、drop 後に新しい checkpoint vector を再利用するため（同 `generate.cpp:13838-13840, 13905-13915`）。

## 実行時の詳細

serve loop の開始時に `CheckpointPool` を作る箇所でスイッチが初回評価される。以後は関数内 static の値を参照するため、リクエスト単位の再読込はしない（`engine/src/program/generate.cpp:566-572, 13838-13840`）。

request が既存 slot の会話を続ける場合、slot 内の checkpoint を main session 側へ移し、そのうち再度 slot に持たせる checkpoint は次の admission で slot に移動する（同 `generate.cpp:19888-19945, 20123-20131, 23692-23724`）。他の slot にある一致 checkpoint は slot 側に残して借用し、main session の履歴と照合して復元元にできる（同 `generate.cpp:19297-19309, 20086-20120`）。移動した checkpoint は main session の `checks` から消える。park 処理は main session の `checks` を対象に snapshot を作るため、移動直後に main session を park するとその checkpoint は snapshot に含まれず、slot 側に残る（同 `generate.cpp:14188-14200, 14519-14526, 23692-23724`）。serve の session-file `SAVE` は `--batch` 使用時に拒否されるため、batch admission で checkpoint を移動した状態を session-file に保存する経路はない（同 `generate.cpp:18613-18617`）。

復元元として slot の checkpoint を使えない場合、通常の prompt cache / conversation cache 経路が選ばれる。checkpoint を見つけられない、または slot state の copy に失敗した場合に prompt 全体を読み直す fallback とログは `engine/src/program/generate.cpp:19863-19875, 20086-20120` にある。restore 自体に失敗した場合は `ERR restoring a conversation checkpoint failed` を stdout に出して処理を `return 1` で終える（同 `generate.cpp:20112-20121`）。

## ログと測定値

環境変数を明示的に指定したことや checkpoint を move したことだけを知らせる専用ログはない。自動設定時は HIP gfx1151 で `strata: gfx1151 (Strix Halo): the exact parallel-request switches are on for ...`、RDNA3 discrete で `strata: gfx11 (RDNA3): exact parallel-request switches on for ...` が stderr に出て、列挙に `SLOT_CKPT_MOVE` が含まれる。Linux CUDA の同じ parallel stack の自動設定は silent と記され、ここでは専用ログを出さない（`engine/src/core/arch_defaults.cpp:248-260, 346-355, 433-442`; `engine/include/strata/core/arch_defaults.hpp:126-130`）。admission 自体は `strata batch: slot %d takes %lld tokens (copied in %.1f ms)` を stderr に出すが、この時間は checkpoint move の有無を個別には示さない（`engine/src/program/generate.cpp:23725-23728`）。

`docs/BATCHING.md:123` は `112 MB` の copy を避けると説明するが、ここではその記述を実測値として一般化しない。同文書の測定は複数の parallel switches をまとめて比較しており、この変数単独の測定値ではない（同 `docs/BATCHING.md:115-123, 133-135`）。

## 根拠

- 値判定・cache: `engine/src/program/generate.cpp:560-572`
- checkpoint pool の有効化: `engine/src/program/generate.cpp:13838-13840, 13905-13915`
- slot / session 間の checkpoint 検索・移動・復元: `engine/src/program/generate.cpp:19291-19341, 19888-19949, 20086-20136, 23673-23724`
- 自動設定: `engine/src/program/generate.cpp:4287-4320, 4410-4414`; `engine/src/core/arch_defaults.cpp:218-260, 346-355, 433-442`; `engine/include/strata/core/gfx11_extra.hpp:116-132`
- park 対象: `engine/src/program/generate.cpp:14188-14200, 14519-14526`
- 関連資料: `docs/BATCHING.md:115-135`
