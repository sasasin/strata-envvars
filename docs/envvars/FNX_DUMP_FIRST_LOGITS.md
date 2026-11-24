# `FNX_DUMP_FIRST_LOGITS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

この変数は、sFNX split engine の `Session::generate` が各 `generate()` 呼び出しで最初に検証した行の全語彙 logits を、float32 の生データとしてファイルに保存する診断用フックである。トークンの選択や生成制御には使わず、通常の生成結果を変える処理はない。読み取り箇所は `engine/src/split/src/session.cpp` のみである（`session.cpp:398-405, 467-481`）。

対象は `STRATA_BUILD_SPLIT` で有効化する独立した `strata-split-*` 実行ファイルの Session 経路である。split engine 自体は opt-in で、通常の `strata` エンジンにはこの読み取り箇所がない（`engine/CMakeLists.txt:922-927`, `engine/src/split/CMakeLists.txt:76-89, 120-129`）。`sfnx` の通常 GEN 処理は `Session::generate` を呼ぶ一方、BGEN は初回トークンを別の `Engine::step` 経路で計算するため、このフックは BGEN の初回トークンを保存しない（`engine/src/split/tools/sfnx.cpp:860-861, 936-953`）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `Session::generate` が最初の `verify` に到達 | `getenv` は null。ファイルを作らない | null 以外なら値全体を出力パスの接頭辞として使用 | 無効値の parse や検証はない |

`std::getenv` の戻り値が null かどうかだけで分岐し、数値変換、文字列比較、空白除去、パス検証はしない。空文字も設定済みとして扱い、`.0`、`.1` のようなファイル名になる。`run/logits` なら `run/logits.0`、値が `0`、`1`、`true`、`false`、`0anything`、または空白だけでも、その文字列を接頭辞として `.0` などへ出力する。未設定以外に無効と判定される値はない。CLI 引数、設定ファイル、別環境変数による上書きや fallback はない（`engine/src/split/src/session.cpp:472-480`）。

## 有効になる条件

- `STRATA_BUILD_SPLIT` が有効で、構成条件を満たした `strata-split-*` バイナリを実行する必要がある。変数自体に CUDA/HIP や OS の個別判定はない（`engine/CMakeLists.txt:922-927`, `engine/src/split/CMakeLists.txt:20-27, 76-89, 120-129`）。
- `Session::generate` が最初の `verify` に到達する必要がある。生成前に prompt 読み込みが失敗するか、`max_new < 1` などで先に例外になる呼び出しでは読み取られない（`engine/src/split/src/session.cpp:398-405, 457-472`）。
- sfnx の BGEN バッチ経路は `Session::generate` を使わず初回トークンを `Engine::step` で処理するため対象外である（`engine/src/split/tools/sfnx.cpp:936-953`）。
- 有効なパスでも、書き込み先を開けない・全量を書けない場合はファイル出力が失敗する。書き込みエラーは警告に留まり、例外や token 選択の変更にはならない（`engine/src/split/src/session.cpp:477-480`）。

## 実行時の詳細

`produced` は `Session::generate` の呼び出しごとに 0 で初期化される。`verify(rows)` の直後、生成 token の選択前に `produced == 0` を確認し、そのとき初めて関数内 static の `dump` と `dump_n` を初期化する。したがって `getenv` はプロセス内で最初にこの地点へ到達したときだけ評価され、値は後続呼び出しで再読込されない。Strata 内に値の再取得や更新処理はない（`engine/src/split/src/session.cpp:398-405, 467-479`）。

値が null でなければ `e_.last_logits(1)` が先頭行を全語彙分取得する。各カードの語彙範囲を連結した `std::vector<float>` であり、各要素は4バイトである。その後、値に `.` とプロセス共通の連番を連結したパスを `fopen(..., "wb")` で開き、行全体をヘッダーなしの float32 生データとして書く。連番は `Session` ごとではなく、この実行ファイル内でこの処理が行われた順に増える。`wb` のため同名ファイルが既にあれば切り詰める。ロケール変換やテキスト形式への変換はない（`engine/src/split/src/session.cpp:472-480`, `engine/src/split/src/engine_common.cu:714-725`）。

logits のコピーが GPU API エラーで失敗した場合、`Engine::last_logits` 内の `ck` が例外を送出する。sfnx の GEN 実行中に伝播した例外は `fail` が stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出して終了コード 1 でプロセスを終了する。ファイルを開けない、または `fwrite` が要求数より短い場合は診断ログを出し、ファイルが開いていれば `fclose` する。`fclose` の戻り値は検査しない（`engine/src/split/src/engine_common.cu:29-31, 714-725`, `engine/src/split/src/session.cpp:477-480`, `engine/src/split/tools/sfnx.cpp:1094-1102, 1160-1166`）。

## ログと測定値

ファイルを開けない場合、または `fwrite` が全 float を書けない場合、stderr に次の文字列を出す（`%s` は生成したパス）。

```text
session: FNX_DUMP_FIRST_LOGITS: cannot write %s
```

ファイル出力の成功ログはない。ソース内にこの診断機能の性能値・測定値はない（`engine/src/split/src/session.cpp:478-480`）。

## 根拠

- `engine/src/split/src/session.cpp:398-405, 467-481` — 呼び出しごとの `produced`、読み取り、初回 verify 後の取得と書き込み。
- `engine/src/split/src/engine_common.cu:714-725` — 全カードの語彙範囲から `T` 行を float32 ベクターへコピー。
- `engine/CMakeLists.txt:922-927`; `engine/src/split/CMakeLists.txt:20-27, 76-89, 120-129` — split の opt-in と実行ファイルへの組み込み。
- `engine/src/split/tools/sfnx.cpp:860-861, 936-953` — GEN の Session 経路と BGEN の初回トークン経路。
- `engine/src/split/tools/sfnx.cpp:1094-1102, 1160-1166` — 実行中例外の `ERR` 出力とプロセス終了。
