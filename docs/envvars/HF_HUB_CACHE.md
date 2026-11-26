# `HF_HUB_CACHE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Strata の Python Control は、この変数を二つの用途で読みます。`strata drafting fetch` やモデル準備で DFlash2 の素材を探すときは、指定された Hugging Face キャッシュ内の固定リビジョンを再利用できるか確認します。また、利用者の GGUF の隣に Strata 用ファイルを置くデータフォルダーを推定するときは、その場所がキャッシュ内かを判定し、キャッシュを Strata の書き込み先に選ばないようにします。エンジンの設定値や推論動作を直接変更する変数ではありません。根拠は `terminal/strata_control/drafting_fetch.py:121-145,376-416` と `terminal/strata_control/discovery.py:455-497` です。

## 値と判定

| 読み取り箇所 | 未設定・空文字 | 設定時 | 判定方法 |
|---|---|---|---|
| DFlash2 素材の検索 (`_hub_snapshots`) | 対象の root を追加しない | 空でない文字列をパスとして追加 | `os.environ.get(name)` の真偽値のみ。文字列形式・存在・絶対パスかの検証はしない。`~` の展開もしない。相対パスはプロセスの作業ディレクトリー基準で使われる。 |
| キャッシュ内判定 (`in_hf_cache`) | root 判定には使わない | 値をパスとして解決し、そのパス自身または配下をキャッシュ内と判定 | 空でない値のみを `Path(...).expanduser().resolve()` する。解決時の `OSError` はその root を無視する。値の大文字小文字や内容を別途検証しない。 |

どちらも `1` / `true` のようなフラグ値を要求しません。空白だけの値も空文字ではないためパスとして扱います。`HF_HUB_CACHE` の後に `HUGGINGFACE_HUB_CACHE`、`HF_HOME`（素材検索ではその `/hub`）、既定のホーム下キャッシュが順に候補になります。素材検索では候補をすべて調べ、キャッシュ内判定でもいずれかの root に一致すれば真です。`HF_HUB_CACHE` だけで他の候補を上書きする優先順位ではありません（`drafting_fetch.py:121-130`; `discovery.py:455-481`）。

## 有効になる条件

- 素材検索で参照するのは、DFlash2 の pack がまだ準備できておらず、通常の固定ファイル一覧を使う処理です。pack が既に準備済みなら `ensure` は先に返るためキャッシュを調べません。素材ファイルが一部しか見つからない場合は、不足分をダウンロードします（`drafting_fetch.py:376-405`）。
- 素材検索の呼び出し経路はセットアップ、明示的な `strata drafting fetch`、起動準備です。この Python のパス判定には backend や build macro による分岐はありません（`terminal/setup.py:9065-9089`; `terminal/strata_cli/drafting_cmd.py:281-305`; `terminal/strata_cli/launch/runner.py:2115-2158`）。
- 素材検索対象は `incoai/Qwen3.8-Flash-Next-DFlash2` の固定 revision `a22a1744e85c17364dcc54a6a420af7135d4c7f6` です。各ファイルは規定サイズと SHA-256 が一致した場合だけ再利用されます。ローカルの作業用 `src` がキャッシュより先に調べられます（`drafting.py:235-253`; `drafting_fetch.py:121-145,391-392`）。
- キャッシュ内判定は、利用者自身の GGUF を指定した起動経路で、隣接データフォルダーを推定するときに使われます。推定先が書き込み不可、またはキャッシュ内なら隣接先を採用せず、Strata が通常使うデータフォルダーへ退避します。明示した `--data-dir` はこの隣接先推定の対象ではありません（`launch/runner.py:1514-1535,1548-1562`; `launch/app.py:311-326`）。
- `models--` で始まるパス要素があれば、環境変数の root と一致しなくてもキャッシュ内と判定します。root 自体またはその子孫である場合も該当します。別名のキャッシュフォルダーは直下に `models--` で始まるディレクトリーを持つ場合に判定されます（`discovery.py:455-481`）。

## 実行時の詳細

両関数とも呼び出されるたびに `os.environ` を参照し、値をモジュール定数や関数内 `static` に保存しません。素材検索では各 root の下に `models--incoai--Qwen3.8-Flash-Next-DFlash2/snapshots/<revision>/` を組み立て、必要ファイルを探します。見つけたファイルは `is_file`、サイズ、SHA-256 を確認し、pack 作成に使います。キャッシュ内の素材は Strata の `src` へコピー・削除せず、pack は指定された Strata のデータフォルダーに作られます（`drafting_fetch.py:121-145,376-442`）。

素材検索は明示的な `strata drafting fetch` のほか、セットアップや起動準備が DFlash2 を必要とするときに `ensure_for` 経由で行われます。通常の起動でも必要に応じて準備されますが、未取得時の失敗は起動全体を止めず、MTP で続行する警告経路があります（`drafting_fetch.py:352-373`; `terminal/setup.py:9065-9089`; `launch/runner.py:2115-2158,3316-3319`; `drafting_cmd.py:281-305`）。

## ログと測定値

`HF_HUB_CACHE` 自体を理由にしたログやエラーはありません。明示 fetch で必要素材が不足し、接続できない場合は `strata: There is no internet connection, so the DFlash2 drafter can't be downloaded now.` を stderr に出して終了コード 5 になります（`drafting_fetch.py:393-396`; `drafting_cmd.py:290-301`）。起動準備では取得失敗時に警告を通知し、MTP などで続行します（`launch/runner.py:2144-2158`）。この環境変数に関する測定値はありません。

## 根拠

- `terminal/strata_control/drafting_fetch.py:121-145,376-442` — キャッシュ root の読み取り、候補 snapshot の組み立て、検証と利用。
- `terminal/strata_control/drafting.py:235-253` — 対象 repository、固定 revision、素材のサイズとハッシュ。
- `terminal/strata_control/discovery.py:455-497` — root とパス構造によるキャッシュ内判定、隣接データフォルダーの選択。
- `terminal/strata_cli/launch/runner.py:1514-1562,1710-1718,2115-2158,3316-3319` — 起動時のフォルダー推定、通知、DFlash2 素材の準備。
- `terminal/strata_cli/launch/app.py:311-326` — アプリの既定フォルダー選択。
- `terminal/strata_cli/drafting_cmd.py:281-305` — 明示 fetch の結果、エラー表示、終了コード。
- `terminal/setup.py:9065-9089` — セットアップからの取得呼び出しと MTP への fallback。
