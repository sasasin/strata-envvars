# `STRATA_STARTUP_UNBUFFERED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows で mmap した expert ファイルを使い、CPU RAM に resident copy を作る起動処理では、GPU expert cache の充填と RAM copy の読み込み中だけファイルを unbuffered read に切り替える。`STRATA_STARTUP_UNBUFFERED=0` を指定すると、この一時切り替えを抑止し、mapped view から読み込む。対象は `FileExpertSource::begin_startup_unbuffered` で、読み込み内容や expert の選択を変える設定ではない。切り替えが始まらない場合は既存の mapped read 経路が続く（`engine/src/core/expert_source.cpp:3032-3042`、`engine/src/program/generate.cpp:8675-8686`）。

## 値と判定

Windows 版の `begin_startup_unbuffered` が呼ばれた時点で `std::getenv` を一度実行する。未設定または空文字列は抑止条件に一致せず、起動時 unbuffered read を試みる。空でない値は `std::atoi` で変換し、結果が `0` のときだけ開始を抑止する。文字列全体の妥当性検査、範囲検査、clamp はない。したがって `0`、`-0`、`false`、`true`、`0anything`、`anything` は変換結果が 0 となり抑止し、`1`、`-1`、`1anything` は非 0 となり抑止しない。`atoi` が受け付ける先頭空白と符号・数字列も変換に使われ、後続文字列は判定されない（`engine/src/core/expert_source.cpp:3032-3037`）。

| 条件 | unset | 起動時 unbuffered read を試みる値 | 抑止する値 |
|---|---|---|---|
| Windows で下記の呼び出し条件を満たす | 試みる | 空でない値で `atoi(value) != 0`（例: `1`, `-1`, `1x`） | 空でない値で `atoi(value) == 0`（例: `0`, `false`, `0x`, `x`） |
| 非 Windows | この関数の判定は実行されない | 該当なし | 該当なし |

## 有効になる条件

- Windows build であること。呼び出し側も `_WIN32` 条件内にあり、他 OS では呼び出されない（`engine/src/program/generate.cpp:8675-8687`）。
- `--mmap-experts` 系の `FileExpertSource` が開かれていること。`--resident-cpu-experts` は `--mmap-experts` と静的 `--expert-profile` を要求する（`engine/src/program/generate.cpp:4870-4871`、`engine/src/program/generate.cpp:8621-8647`）。
- `o.resident_cpu_experts` が有効で、通常の file tier がすでに unbuffered ではないこと。`--resident-experts` は mmap と resident CPU copy を有効にする（`engine/src/program/generate.cpp:4220-4224`、`engine/src/program/generate.cpp:8678-8680`）。
- 値が空でなく `atoi(value) == 0` の場合は、この一時切り替えを開始せず、mapped read のまま進む。CLI からこの環境変数の判定を上書きする処理は見つからなかった（`engine/src/core/expert_source.cpp:3032-3037`）。

## 実行時の詳細

環境変数は起動処理中の `begin_startup_unbuffered` 呼び出し時に読む。関数内の static cache はなく、この呼び出しでの判定に使われる（`engine/src/core/expert_source.cpp:3032-3037`）。呼び出し側は `--resident-cpu-experts` の RAM copy 処理に入る前に判定する。値が抑止を指すと関数は `false` と理由 `STRATA_STARTUP_UNBUFFERED=0` を返し、呼び出し側はその理由を含む mapped-read ログを意図的に出さない（`engine/src/program/generate.cpp:8675-8686`）。

抑止されず、ファイルが open 済みで mapped view があり、すでに unmapped / startup unbuffered でなく、file tier 自体が unbuffered でない場合に処理を試みる。最初の blob を mapped read と unbuffered read の両方で比較し、一致すれば `startup_ub_` を立て、GPU cache の充填と resident RAM copy が終わるまで mapped view / handles を閉じる。全 startup reads の後に `end_startup_unbuffered` が view を再 map し、成功すれば unbuffered handles と stage buffers を閉じて通常の mapped 経路に戻る（`engine/src/core/expert_source.cpp:3038-3104`、`engine/src/core/expert_source.cpp:3107-3130`、`engine/src/program/generate.cpp:12077-12117`）。

既に unbuffered である場合、source が未 open、map がない場合などは開始しない。先頭 blob の比較や direct open が失敗した場合は view の再 map を試す。再 map に成功すれば mapped 経路へ戻るが、再 map 自体が失敗した場合は失敗理由にその内容を加える。`end_startup_unbuffered` で再 map に失敗した場合は unbuffered handles を維持し、以後の file tier read も unbuffered のままとなる（`engine/src/core/expert_source.cpp:3038-3042`、`engine/src/core/expert_source.cpp:3053-3100`、`engine/src/core/expert_source.cpp:3107-3114`）。

この変数は `STRATA_UNBUFFERED_LOAD` の file tier 選択を変更しない。そちらの処理は `src.set_unbuffered` の後にあり、この変数は Windows の resident CPU copy に伴う startup 区間だけを制御する（`engine/src/program/generate.cpp:8654-8673`）。

## ログと測定値

- startup unbuffered 開始成功時: `strata generate: the GPU cache's fill and the RAM copy read unbuffered (%s)`。`%s` は成功時の elapsed time を含む理由文字列（`engine/src/program/generate.cpp:8680-8682`、`engine/src/core/expert_source.cpp:3087-3090`）。
- `atoi(value) == 0` で抑止した場合、この変数名を含む `why` を見て mapped-read のログを省略する。これは開始拒否やプロセス終了ではない（`engine/src/core/expert_source.cpp:3034-3037`、`engine/src/program/generate.cpp:8683-8685`）。
- 適用条件を満たすが別の理由で開始できない場合: `strata generate: the GPU cache's fill and the RAM copy read through the mapping (%s)`（同上）。
- startup 後に再 map できない場合は `strata generate: WARNING: %s` を出し、file tier を unbuffered のまま維持する。再 map 成功時は `strata generate: the startup reads are done: experts.bin mapped again (%.0f ms)` を出す（`engine/src/program/generate.cpp:12108-12117`）。
- Strata の `docs/DETAILS.md` にこの変数の説明や測定値は見つからなかった。ここでは性能効果を推定しない。

## 根拠

- `engine/src/core/expert_source.cpp:3032-3104` — 値の判定、Windows 限定の開始処理、先頭 blob の probe と失敗時の復旧。
- `engine/src/core/expert_source.cpp:3107-3130` — startup 完了後の map 復帰と unbuffered resource の解放。
- `engine/src/program/generate.cpp:4870-4871`, `8621-8647`, `8675-8687` — CLI 条件、source open 後の呼び出し条件とログ。
- `engine/src/program/generate.cpp:12077-12117` — resident copy 後の startup unbuffered 終了処理と観測ログ。
- `engine/include/strata/core/expert_source.hpp:947-956` — API の説明と `startup_unbuffered` 状態。
